# Operación

Guía para poner esto a marcar archivos de verdad.

## La regla que más importa

**Normalizá las imágenes a 1024 px de lado largo antes de marcarlas.**

Con eso, el archivo llega al verificador a su resolución de marcado y la escala
es 1.0: no hay búsqueda que hacer. La extracción baja de 2–20 s a **0.2 s** y
desaparece el único modo de fallo que queda (que el buscador de escala se
enganche a un patrón periódico de la propia imagen).

```python
from PIL import Image
img = Image.open(src)
img.thumbnail((1024, 1024), Image.Resampling.LANCZOS)   # nunca amplía
marcada = codec.embed(np.asarray(img.convert("RGB")), ident, km)
```

Y en la verificación, `search_scale=False` cuando sepas que el archivo no pasó
por un canal que reescale.

## Marcá cada rendition, no el original

Una plataforma genera miniaturas y versiones reducidas. Si marcás solo el
original, las copias que efectivamente circulan salen **sin marca**. El marcado
va después del resize de la plataforma, una vez por rendition.

Cada rendition puede llevar su propio identificador, lo que además te dice qué
versión se filtró.

## Multi-cliente: usá `tenant`

```python
km = derive(passphrase_maestra, tenant=b"cliente-42")
```

`tenant` deriva solo la llave de cifrado; el layout (y por tanto la sincronía) es
común. Verificar un archivo de origen desconocido cuesta **una** sincronía y
luego N intentos de descifrado baratos, en vez de N sincronías completas más N
derivaciones Argon2id de 64 MiB.

Si en cambio das a cada cliente una passphrase distinta, cada verificación
multiplica su coste por el número de clientes.

## Qué embeber: nunca el identificador real

Embebé un identificador **seudónimo** de 16 bytes que solo tu cliente pueda
resolver contra su propia tabla:

```
id_embebido (16 B aleatorios) ──► tabla del cliente ──► usuario, sesión, fecha
```

Meter el ID de usuario o un correo dentro del archivo convierte un producto de
cumplimiento en un incumplimiento de protección de datos. El identificador
aleatorio no dice nada por sí solo y se revoca borrando una fila.

## Elegir `delta`

`delta` es el compromiso entre imperceptibilidad y robustez. La cota de diseño es
`Δ ≥ 2·q_k(Q_min) + 4`, con `q_k` el paso de cuantización JPEG de los portadores:

| Perfil | `delta` | PSNR (Y) | Sobre |
|---|---|---|---|
| Estándar | 26 | ≈ 42 dB | JPEG Q ≥ 40 |
| Robusto | 42 | ≈ 39 dB | JPEG Q ≥ 30 |

Q20 no lo aguanta ningún perfil probado.

## Elegir `template_amp`

Es la otra mitad del presupuesto de distorsión, y durante un tiempo fue la mayor:
a Δ=26 la plantilla aportaba el **66 %** de la energía de error y el QIM el 34 %.

| Perfil | `template_amp` | Efecto |
|---|---|---|
| Códec | 2.0 | Calibrado sobre imágenes sintéticas; sobre fotografías la sincronía flojea en recortes chicos |
| Demo web | 5.0 | Punto de operación actual, **con enmascaramiento y `floor` 0.12**: seis ataques al 100 % y los dos recortes chicos al 97 % sobre 30 intentos, PSNR 39.27 dB |
| — | 6.0 | También 8/8, pero sin máscara es lo que producía el moteado reportado |

Desde el enmascaramiento perceptual (`image/masking.py`) la amplitud ya no se
aplica plana: se reparte según la textura del contenido. **La máscara no cuesta
robustez** —a igual amplitud da la misma tasa y el mismo PSNR—, así que lo que se
paga al bajar la amplitud es sólo lo que cuesta bajarla: a 4.0 los recortes de
400 y 256 px caen al 66 %, a 5.0 vuelven al 100 %.

**No ajustes la amplitud sola.** Subirla devuelve moteado, y el PSNR no lo ve: lo
que se lee como un filtro es estructura de escala gruesa en zonas planas. La otra
palanca es `masking.DEFAULTS["floor"]` —la ganancia mínima, o sea cuánta plantilla
queda en lo perfectamente liso—: bajarla de 0.35 a 0.12 saca marca de ahí sin
tocar la textura, que es de donde sale la sincronía, y eso es lo que permite
sostener amp 5.0 con menos nube que el perfil de 4.0. `knee` sí conviene dejarlo
quieto: a 9.0 mejora la nube pero el recorte de 256 px cae de 9/9 a 7/9.

Las dos cosas **hay que medirlas** cada vez: mirá la `z` que devuelve `extract` y
el error en zona plana que imprime `tools/comparar_visibilidad.py`, no sólo el
PSNR. Y si cambiás el perfil, volvé a correr `web/tasas.py` — el servidor se
niega a mostrar en pantalla tasas medidas con otra configuración.

Medí primero la calidad real de tu canal con `tools/measure_channel.py` y fijá
`delta` con ese número, no con un supuesto.

## Qué guardar en tu sistema

| Dato | Dónde |
|---|---|
| La passphrase | Gestor de secretos. **Nunca** en disco junto a los archivos |
| El identificador embebido | Tu base de datos, con lo que resuelve |
| `delta` y `base_long` usados | Con el registro del archivo: hacen falta para verificar |

Los parámetros de perfil son públicos y no son un secreto: el extractor ciego no
puede leerlos del archivo antes de sincronizar, así que tienen que estar fijados
de antemano. Lo secreto es la passphrase.

## Rendimiento

| Operación | Imagen 1024 px | Imagen 2400 px |
|---|---|---|
| Marcado | ≈ 0.2 s | ≈ 3 s |
| Verificación, escala 1.0 | ≈ 0.2 s | ≈ 0.3 s |
| Verificación con búsqueda de escala | 1–3 s | 2–20 s |

La búsqueda de escala es lo caro. La verificación es un proceso forense y
diferido, no un camino crítico: 20 s por un caso difícil es aceptable, pero
normalizar a 1024 px al marcar los evita casi todos.

El marcado es vectorizado (`einsum` sobre todos los bloques); el coste crece
linealmente con los píxeles.

## Cómo responder cuando no hay marca

El sistema devuelve exactamente tres resultados:

| Resultado | Qué podés afirmar |
|---|---|
| `id=...` | Este archivo salió de la copia con ese identificador. El tag AEAD lo garantiza (falso positivo 2⁻¹²⁸) |
| `sin marca legible` | **Nada.** Puede ser un archivo ajeno, o uno propio degradado |
| `ID INCORRECTO` | No debería ocurrir nunca. Si ocurre, es un fallo grave: reportalo |

Confundir el segundo caso con "no es tuyo" es la forma más rápida de que un
cliente pierda un caso usando la herramienta.

## Límites que hay que declarar al cliente

- **Rotación no soportada.** Ni escalado no uniforme, ni cizalla.
- **JPEG Q20 no soportado.**
- **Recorte mínimo**: ~256 px de lado si marcás a 1024 px. Si marcás una imagen
  de 2400 px sin normalizar, el piso sube a ~600 px nativos, porque la tesela
  mide 300 px nativos y hacen falta al menos dos.
- **Imágenes con patrón periódico fuerte** (rejas, fachadas repetitivas,
  tableros) pueden desviar el buscador de escala hacia el patrón de la propia
  imagen. Normalizar a 1024 px lo evita.
- **La marca vive en la luminancia.** Convertir a escala de grises no la afecta;
  cambios de brillo o contraste fuertes sí.
