# Registro de Procedencia — interfaz de demo

Tres pantallas, una cosa en cada una:

| Pestaña | Qué hace |
|---|---|
| **Firmar** | Escribís a nombre de quién y el título, soltás la imagen, la marca, te la podés descargar |
| **Verificar** | Soltás cualquier imagen recibida —**sin contraseña**— y devuelve quién la marcó, cuándo y qué es |
| **Pruebas** | La batería de ocho ataques de canal sobre lo que acabás de firmar |

Todo contra el códec real de `src/stego`: ningún número de la pantalla está
escrito a mano.

## El demo que convence

1. **Firmar** → soltás la foto → descargás `marcada-xxxxxxxx.png`.
2. Se la mandás a alguien **por WhatsApp de verdad**, y esa persona te la reenvía.
3. Guardás lo que te llegó y lo soltás en **Verificar**.
4. Sale **«marcada por <lo que escribiste>, 22 de agosto, 9:52 p. m.»**. La
   Content Credential, no.

`Verificar` no sabe qué código esperar ni de quién. Por eso el paso 3 prueba
algo que el jurado no puede sospechar que está arreglado.

## Por qué verificar no pide contraseña

ChaCha20-Poly1305 es simétrico: **quien puede verificar también puede
falsificar**. Entregarle la passphrase al ciudadano para que compruebe una imagen
sería entregarle la capacidad de fabricar marcas de esa entidad. Por eso la
verificación es un servicio y no una operación local: la llave del registro vive
en el servidor y no sale.

## Quién marcó: un campo, no una llave

Hay **una** llave para todo el registro (`LLAVE_REGISTRO`) y el nombre de quien
marca se escribe libre en el formulario y queda en el asiento, igual que el
título. Los 16 bytes son el código, el código resuelve una fila del registro, y
la fila dice el nombre.

Antes había tres emisores fijos, cada uno un *tenant* con su propia `k_cipher`,
y para saber quién marcó se probaba la llave de cada uno por turno. Eso
demostraba la separación multi-tenant del códec, pero ataba la identidad a la
criptografía: con nombres libres no escala, porque cada nombre nuevo sería una
llave más que probar y el caso «sin marca» ya cuesta segundos. De paso, ese caso
bajó a una sola búsqueda en vez de tres.

La separación multi-tenant **sigue existiendo en el códec** —`keys.derive` acepta
`tenant`— y con ella un verificador revisa N clientes pagando una sola sincronía.
Lo que ya no hace es esta demo.

> **La demo no autentica a nadie.** Cualquiera escribe cualquier nombre. En un
> sistema real eso es una cuenta con credenciales; acá es un campo de texto.

La passphrase del registro sale de `STEGO_REGISTRO`; el default es solo para la
demo. Los asientos se guardan en `web/registro.json` (fuera de git).

## Arrancar

```bash
.venv/bin/pip install fastapi "uvicorn[standard]" python-multipart
.venv/bin/python -m uvicorn web.server:app --port 8000
```

Abrir <http://127.0.0.1:8000>.

## Chequeo antes de presentar

**Corrélo con la imagen que vayas a proyectar.**

```bash
.venv/bin/python web/check.py fotos/la-que-voy-a-usar.jpg --firmas 3
```

Falla si algún ataque deja de recuperar el identificador exacto en todas las
firmas, o si una passphrase incorrecta devuelve algo.

Varias firmas y no una: `payload.pack` usa un nonce nuevo por firma, así que cada
firma produce una imagen marcada distinta. Cerca del margen eso decide entre
recuperar y no, y una sola corrida no distingue «funciona» de «tuve suerte».

## El perfil de la demo: `template_amp = 5.0` con enmascaramiento

El default del códec (2.0) está calibrado sobre imágenes sintéticas, donde la
plantilla de sincronía no compite con nada. Sobre una fotografía el espectro del
contenido la tapa: la `z` cae de ~5.7 a ~3.4 y los recortes chicos dejan de
recuperar. De ahí que la demo suba la amplitud.

Pero subirla tiene un precio visible, y a 6.0 se pagó entero: la plantilla **se
veía**, como un moteado en cielos y paredes. A esa amplitud inyecta un RMS de
2.29 niveles de gris con picos de ±6.9, en un patrón periódico exacto de 64 px y
sumado con amplitud constante a **todos** los píxeles. Reparto de la energía de
error a Δ=26: plantilla 66 %, QIM 34 %.

La respuesta fueron dos cambios —bajar la amplitud y modular la plantilla por
enmascaramiento perceptual (`stego/image/masking.py`)—, y conviene saber cuál de
los dos hace qué, porque no es lo que parece. Medido sobre 3 fotografías, 3
firmas, separando las dos palancas:

| perfil | PSNR | recorte 400×300 | recorte 256×256 |
|---|---|---|---|
| 6.0 sin máscara | 38.21 dB | 100 % | 100 % |
| 4.0 sin máscara | 40.46 dB | 100 % | 66 % |
| 6.0 **con** máscara | 38.21 dB | 100 % | 100 % |
| 4.0 con máscara | 40.43 dB | 66 % | 66 % |

**El enmascaramiento no cuesta robustez**: a igual amplitud da la misma tasa y el
mismo PSNR. Lo que se llevó los recortes fue bajar la amplitud, y la máscara sólo
amplifica ese coste cuando ya no queda margen.

### El PSNR no mide lo que se veía

Subir la amplitud recupera recortes pero devuelve moteado, y **el PSNR no lo
distingue**: lo que se leía como un filtro era estructura de *escala gruesa* en
zonas planas, no error total. La medida que sí corresponde es el error tras
pasa-bajos (σ=3, que es lo que el ojo integra) restringido a zona plana. Tomando
como 100 % el perfil que produjo el problema:

| perfil | nube en zona plana | recorte 400 / 256 |
|---|---|---|
| 6.0 sin máscara | **100 %** ← el problema | 100 % / 100 % |
| 4.0 con máscara, `floor` 0.35 | 49 % | 66 % / 66 % |
| 5.0 con máscara, `floor` 0.35 | 58 % | 100 % / 100 % |
| **5.0 con máscara, `floor` 0.12** | **45 %** | **100 % / 100 %** |

Por eso el perfil no es sólo una amplitud: va con `masking.DEFAULTS["floor"]`
bajado de 0.35 a **0.12**. El floor es la ganancia mínima de la máscara, o sea
cuánta plantilla queda en lo perfectamente liso; bajarlo saca marca de ahí sin
tocar la textura, que es de donde el sincronizador saca la señal. Con eso la nube
queda **por debajo del arreglo original** y los recortes vuelven al 100 %.

`knee` en cambio no se toca: a 9.0 mejora la nube pero el recorte de 256 px cae
de 9/9 a 7/9.

Medición final del perfil de la demo, 3 fotografías × 10 firmas = **30 intentos
por ataque**, PSNR 39.27 dB:

| ataque | tasa |
|---|---|
| Sin ataque · JPEG Q75 · recorte 800×600 · reescalado ×0.75 · canal WhatsApp · recorte grande + canal | 30/30 — **100 %** |
| Recorte 400×300 | 29/30 — **97 %** |
| Recorte 256×256 | 29/30 — **97 %** |

Ese 97 % **no es un coste del `floor`**: los dos recortes chicos están en el
margen y lo decide el nonce de `payload.pack`, así que la cifra se mueve entre
corridas con el perfil idéntico —30/30 en una tanda, 29/30 en la siguiente—. En
un barrido dedicado de 30 firmas, floor 0.35, 0.25, 0.18 y 0.12 dieron **30/30
los cuatro**, con la `z` de sincronía cayendo apenas de 3.71 a 3.64.

Se muestra 97 % y no se redondea a 100: una tasa que falla una vez de treinta
tiene que estar declarada antes de subir a tarima, no descubrirse ahí.

Reproducir la comparación visual con `tools/comparar_visibilidad.py`, que además
imprime el error separando zona plana de textura.

## Tasas medidas en pantalla

```bash
.venv/bin/python web/tasas.py fotos/*.jpg --firmas 5
```

Escribe `web/tasas.json`, que la interfaz lee para mostrar el porcentaje junto a
cada ataque. Así un fallo en tarima es un resultado declarado y no una sorpresa.
Si el archivo no está, la interfaz no muestra ningún porcentaje: no inventa
ninguno.

## Verificación en dos pasos

`/api/cotejar` prueba primero **escala nativa** y solo busca escala si el AEAD no
valida. El criterio de reintento es que la trama no autentique, nunca una
comparación contra el identificador esperado —un verificador real no lo conoce—.
Importa por dos razones medidas: la búsqueda tarda entre 10 y 100 veces más, y a
veces se engancha con una escala espuria cuando la `z` queda baja.

**Decir que no cuesta más que decir que sí.** Con marca, el camino rápido resuelve
en 0.06–0.4 s. Sin marca hay que agotar la búsqueda antes de concluir: unos 9 s.
`/api/verificar` normaliza la entrada a 1024 px antes de buscar —el registro marca
a esa resolución— y eso baja el caso negativo de 17.3 s a 9.4 s sin cambiar ningún
resultado positivo. Con una sola llave el «sin marca» se resuelve en esa única
búsqueda, en vez de los ~13 s que costaba probando tres emisores.

`/api/verificar` distingue tres estados, y ninguno acusa:

| estado | qué significa |
|---|---|
| `verificado` | la marca es de un emisor registrado y el radicado tiene asiento |
| `sin_asiento` | la marca es auténtica pero ese radicado no figura en este registro |
| `sin_marca` | no se pudo leer ninguna marca. **No prueba que el archivo sea ajeno** |

## Manejo en tarima

Todo con teclado, sin mouse:

No hay barra de atajos en pantalla —el operador ya los sabe y la pantalla no
tiene por qué cargar con la chuleta—:

| Tecla | Acción |
|---|---|
| `1` `2` `3` | Firmar · Verificar · Pruebas |
| `→` / `Espacio` | en Pruebas: siguiente ataque, y cotejarlo |
| `←` | ataque anterior (sin volver a cotejar) |
| `Enter` | cotejar el ataque activo |
| `Esc` | soltar el foco del campo |

Un ataque ya cotejado se muestra desde memoria: volver atrás no vuelve a correr
el códec.

También podés arrastrar la imagen directamente sobre la cartulina.

## Elegir la imagen

**Usá una fotografía.** Evitá texturas de periodo corto y regular —tramas,
tableros, patrones repetidos densos—: desvían el buscador de escala hacia la
periodicidad de la propia imagen. Está documentado en
[`docs/resultados.md`](../docs/resultados.md) y se puede reproducir.

Y pasala por `web/check.py` antes. No confíes en que ande porque anduvo con otra.

El servidor normaliza a 1024 px de lado largo antes de marcar, que es la
recomendación de [`docs/operacion.md`](../docs/operacion.md): más rápido y más
fiable.

## Endpoints

| Método | Ruta | Qué hace |
|---|---|---|
| `GET` | `/api/ataques` | lista los ocho ataques con su cadena de operaciones |
| `POST` | `/api/firmar` | `imagen`, `emisor` (nombre libre), `titulo`, `enlace`, `delta`, `template_amp`, `template_mask` → token, código, asiento, lámina |
| `POST` | `/api/cotejar` | `token`, `clave`, `passphrase` → veredicto, id recuperado, diagnósticos, lámina atacada |
| `POST` | `/api/verificar` | `imagen` **y nada más** → estado, constancia (quién, cuándo, qué), código, diagnósticos |

Los endpoints son síncronos a propósito. FastAPI los corre en su threadpool, así
que una extracción lenta no bloquea el event loop.

## Lo que la interfaz no hace

- **No dice que una imagen sea falsa.** Solo «identificador recuperado» o «sin
  marca legible». La ausencia de marca no prueba nada.
- **Casi no guarda nada.** El registro es un `registro.json` sin índice ni
  respaldo; las láminas firmadas viven en un dict en memoria y se pierden al
  reiniciar.
- **No autentica al emisor.** Cualquiera que llegue al formulario puede firmar a
  nombre de cualquier emisor de la lista. En un sistema real eso es una cuenta con
  credenciales; acá es un `<select>`.
- **No debe exponerse a la red.** Sin autenticación, sin límite de tamaño de
  subida, sin CORS configurado.

