# Uso

## Instalación

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # codec + pruebas
.venv/bin/pip install -e ".[dev,web]"    # + la demo web
```

Dependencias del núcleo: `numpy`, `scipy`, `pillow`, `reedsolo`, `cryptography ≥ 44`
(por `Argon2id` y `ChaCha20Poly1305`). No usa OpenCV: Pillow cubre JPEG con
control de calidad y da acceso a la tabla de cuantización.

Extras: `[web]` para la demo (`fastapi`, `uvicorn`, `python-multipart` —este
último lo exige FastAPI para `Form` y `UploadFile`), `[dev]` para las pruebas y
`[legacy-audio]` solo para el código de audio original, que arrastra torch y
unos 3 GB de paquetes nvidia y conserva los defectos auditados.

```bash
.venv/bin/python -m uvicorn web.server:app --port 8000
```

## Línea de comandos

### Marcar

```bash
stego embed --in foto.jpg --out marcada.png --passphrase "..."
```

| Opción | Por defecto | Qué hace |
|---|---|---|
| `--in` | — | Imagen de entrada (JPEG, PNG, cualquier formato que lea Pillow) |
| `--out` | — | Salida. `.png` guarda sin pérdida; `.jpg` usa `--jpeg-quality` |
| `--id` | aleatorio | 16 bytes en hexadecimal (32 caracteres) |
| `--passphrase` | `$STEGO_PASSPHRASE` | Passphrase; conviene pasarla por entorno |
| `--tenant` | `""` | Identificador de cliente: separa la llave de cifrado sin cambiar el layout |
| `--delta` | 26.0 | Paso del cuantizador. Mayor = más robusto y menos imperceptible |
| `--template-amp` | 2.0 | Amplitud de la plantilla de sincronía. Mayor = recupera recortes más chicos y se nota más. La demo web usa **5.0** (con enmascaramiento y `floor` 0.12) |
| `--no-mask` | — | Desactiva el enmascaramiento perceptual de la plantilla. Solo para comparar en el banco: con la máscara activa la marca se ve bastante menos en cielos y paredes |
| `--jpeg-quality` | 95 | Solo si la salida es JPEG |

Imprime el identificador que quedó dentro. **Guardalo**: es lo que después vas a
resolver contra tu propia tabla.

### Verificar

```bash
stego extract --in recibida.jpg --passphrase "..."
```

Salida:

```
z=10.46 escala=1.0000 pilotBER=0.000 borrados=0 copias=35
id=00112233445566778899aabbccddeeff
```

Código de salida `0` si encontró la marca, `1` si no. Cuando no la encuentra:

```
sin marca legible: llave incorrecta o imagen demasiado danada
```

Nunca dice "este archivo no es tuyo": la ausencia de marca no prueba nada.

### Verificar con análisis de integridad

```bash
stego verify --in recibida.jpg --passphrase "..."
```

Hace lo mismo que `extract` y además dice si la imagen fue **editada localmente**,
y dónde:

```
z=5.76 escala=1.0000 ganancia=1.00 pilotBER=0.000
id=0123456789abcdef0123456789abcdef
INTEGRIDAD: alterada — 83 de 768 celdas de 32 px (10.8% de la imagen)
................................
.........############...........
.........############...........
.........############...........
................................
```

`--cell-blocks` ajusta la resolución del análisis, en bloques de 8 px. Por
defecto 4 (celdas de 32 px). Una celda mayor promedia mejor y da menos falsas
alarmas; una menor detecta ediciones más pequeñas.

**Leelo bien**: `id=...` dice de qué copia salió el archivo. La línea de
integridad es lo único que habla de si fue modificado, y solo detecta ediciones
locales por encima del tamaño de celda.

### Diagnósticos

| Campo | Qué significa |
|---|---|
| `z` | Fuerza de la correlación con la plantilla de sincronía. Por debajo de ~5 la sincronía no se enganchó |
| `escala` | Factor aplicado para volver al paso nominal. 1.0 = la imagen llegó a su resolución de marcado |
| `pilotBER` | Fracción de bits piloto mal leídos. **0.000 en toda extracción correcta**; es el indicador más útil |
| `borrados` | Símbolos marcados como borrados antes de decodificar |
| `copias` | Cuántas veces se vio cada posición de la tesela |

## API de Python

```python
from stego.keys import derive
from stego.covers import image_dct_qim as codec
import numpy as np
from PIL import Image

km = derive("passphrase-larga", tenant=b"cliente-42")

rgb = np.asarray(Image.open("foto.jpg").convert("RGB"))
marcada = codec.embed(rgb, identifier_16_bytes, km)          # -> uint8 (H, W, 3)

ident, diag = codec.extract(np.asarray(Image.open("recibida.jpg").convert("RGB")), km)
if ident is None:
    print("sin marca:", diag.reason)
```

`embed` acepta además `delta`, `template_amp` y `base_long`.
`extract` acepta `delta`, `template_amp`, `payload_len` y `search_scale`.

**`search_scale=False`** salta toda la búsqueda de escala. Si controlás el
pipeline y sabés que la imagen llega a su resolución de marcado, esto baja la
extracción de segundos a décimas.

## Herramientas

### Medir un canal real

```bash
python tools/measure_channel.py --make-probes probes/
# mandar las sondas por el canal, guardar lo recibido
python tools/measure_channel.py --compare probes/ recibidas/
```

Reporta, para cada tamaño de entrada: tamaño de salida, factor de reescalado,
calidad JPEG estimada y submuestreo de croma. El estimador de calidad invierte
la escala de la IJG y está validado contra JPEG de calidad conocida (da 30, 50,
75 y 90 exactos).

Con esos números se fijan `--delta` y `base_long`. No los supongas.

### Prueba de extremo a extremo

```bash
python tools/whatsapp_test.py prepare --in fotos/ --out prueba/ --passphrase "..."
# mandar prueba/enviar_*.jpg, guardar lo recibido en prueba/recibidas/
python tools/whatsapp_test.py check --dir prueba/ --passphrase "..."
```

`prepare` marca cada foto con un identificador aleatorio distinto, recorta
800×600 en el desplazamiento (13, 37) y deja un `manifest.json`. `check` verifica
cada archivo recibido contra su identificador y reporta la tasa de acierto.

Distingue tres resultados: `OK`, `sin marca` y `ID INCORRECTO`. El tercero sería
un fallo grave —el AEAD debería hacerlo imposible— y por eso se reporta aparte.

## Pruebas

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 .venv/bin/python -m pytest
```

La variable de entorno evita que pytest cargue plugins ajenos del sistema.
