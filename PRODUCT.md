# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

HTML/CSS/JS plano servido por FastAPI, sin build step. Un solo proceso
(`uvicorn`) sirve la página y expone los endpoints que llaman al códec Python de
`src/stego`. Elegido por el usuario sobre Vite+React: la demo corre en vivo en
tarima y cada dependencia extra es superficie de fallo.

## Users

**Usuario primario:** el equipo que presenta el proyecto en un hackathon de AI
Security (Bogotá, 23 de agosto de 2026). Opera la interfaz en vivo desde un
proyector, en sala iluminada, narrando mientras la maneja. La audiencia es un
jurado que evalúa originalidad, ambición, ejecución, aspecto técnico e impacto.

**Trabajo que hace:** firmar una imagen delante del jurado, someterla a una
batería de ataques reales de canal, y mostrar que el identificador de 16 bytes
se recupera exacto en cada caso.

**Audiencia secundaria (no confirmada como usuario del software):** entidades
emisoras que firmarían sus imágenes y verificadores que las comprobarían. El
producto no tiene todavía una interfaz para ellos.

## Product Purpose

Demostrar que una marca de procedencia que vive **dentro de los píxeles**
sobrevive al canal por el que realmente circulan las imágenes —recorte,
reescalado, recompresión JPEG, borrado de metadatos— mientras el marcado por
metadatos (C2PA / Content Credentials), que es el mecanismo mayoritario para
cumplir el Artículo 50 del AI Act, se destruye en el primer reenvío.

Éxito = el jurado ve el identificador recuperarse, exacto, después de que la
imagen fue visiblemente destrozada.

**Categoría: control + verificación, no diagnóstico.** El sistema no detecta ni
estima nada: registra en el momento cero y comprueba después. Un detector se
equivoca; un registro no — de ahí que no haya falsos positivos. *Control* = al
subir o descargar, el archivo queda marcado; *verificación* = dado un archivo,
devuelve quién y cuándo.

## Positioning

Lo que un producto vecino no podría copiar honestamente:

- **Registro, no detector.** La diferencia de categoría, y la que sostiene todo
  lo demás. Un detector estima a posteriori y se equivoca en las dos direcciones;
  esto registra en el momento cero. El tag AEAD es el **único criterio de
  aceptación**, con probabilidad de falso positivo **2⁻¹²⁸**, y el banco mide **0
  falsos positivos** con passphrase incorrecta.
- **Criterio binario de recuperación exacta.** El resultado es el identificador
  de 16 bytes o nada. No hay "porcentaje de bits correctos" — sin corrección de
  errores un solo bit malo rompe el descifrado, así que un 95% no recupera nada.
- **Los límites están medidos y declarados**, no escondidos: JPEG Q20 fuera de
  alcance, rotación no soportada, recorte mínimo ~256 px marcando a 1024 px.
- **Multi-tenant con una sola búsqueda de sincronía.** El layout deriva de
  `k_chaos` compartido y el cifrado de `k_cipher` por tenant (`keys.derive`), así
  que un verificador revisa N clientes sin pagar N sincronías, y ningún cliente
  puede leer ni falsificar las marcas de otro. *Es una capacidad del códec; la
  demo web ya no la ejercita —usa una sola llave y el nombre de quien marca es un
  campo del registro, porque con nombres libres probar una llave por nombre no
  escala.*
- **Procedencia del hallazgo.** El sistema anterior del que salió éste publicaba
  11 de 18 ataques superados cuando el número real era 0 de 18; la causa raíz
  está identificada y documentada (`docs/auditoria.md`, C6).

## Applications

Tres aplicaciones del mismo mecanismo. Las dos primeras las sostiene el sistema
tal como está; la tercera **hay que enunciarla con su piso medido**.

**1. Trazabilidad de fugas.** Cada descarga sale marcada con el identificador de
quien la bajó. Si el archivo aparece afuera, se sabe de qué usuario salió.
*Problema:* se filtró contenido y la investigación no concluye nunca.
*Cliente:* medios, estudios, farmacéuticas, cualquiera que comparta material
confidencial.

**2. Marcado de contenido subido a plataforma.** Todo lo que un usuario sube queda
marcado con su identificador y la fecha, dentro del archivo.
*Problema:* llega un reclamo legal por contenido alojado y no se puede probar
quién lo subió ni cuándo; los logs se cuestionan, el archivo no.
*Cliente:* marketplaces, plataformas de UGC, clasificados, plataformas de video.

**3. Detección de edición local.** El **cotejo por región**
(`src/stego/integrity.py`) compara la marca celda por celda y señala dónde no
coincide.
*Problema:* sostener que una foto no fue manipulada después de emitida.
*Cliente:* aseguradoras (fotos de siniestro), peritaje, auditoría, notariado.

> ⚠️ **Cómo NO enunciar la aplicación 3.** «Se inserta el hash del propio archivo
> dentro del archivo» describe algo imposible: insertar el hash altera el archivo
> y el hash deja de coincidir consigo mismo. El payload son **16 bytes
> aleatorios**, no un hash, y eso es deliberado —`docs/operacion.md`: meter datos
> reales dentro del archivo «convierte un producto de cumplimiento en un
> incumplimiento de protección de datos»—.
>
> Y el alcance real es acotado: detecta edición **local desde ~160 px de lado**;
> por debajo puede pasar, y **un cambio uniforme sobre toda la imagen no se
> distingue del canal**. Para peritaje eso se declara, no se promete. Nunca «prueba
> que no fue manipulada»; siempre «detecta edición local, con este piso medido».

## Operating Context

- **Escena física:** tarima, proyector, sala con luz encendida, lectura a ~5
  metros. El presentador maneja; nadie más toca la interfaz durante la demo.
- **Después de la demo** el jurado puede acercarse a probar en la laptop, así que
  el detalle no puede estar escondido detrás de la narración.
- Tiempo de pitch corto: la secuencia firmar → atacar → verificar tiene que caber
  en menos de un minuto sin que el operador improvise.

## Capabilities and Constraints

**Lo que hace el códec** (`src/stego/covers/image_dct_qim.py`):

- `embed(rgb, ident_16B, km, delta=...)` → imagen marcada.
- `extract(rgb, km, delta=...)` → `(bytes | None, Diagnostics)`.
- `Diagnostics`: `z`, `scale`, `pilot_ber`, `erasures`, `gain`, `tiles_seen`,
  `ok`, `reason`.
- Cadena: id 16 B → zlib → ChaCha20-Poly1305 → Reed-Solomon(84,44) → QIM sobre
  DCT 8×8 → tesela de 128 px repetida + plantilla aditiva periódica.
- Llaves: passphrase → Argon2id → HKDF → `(k_cipher, k_chaos)`.

**Batería de ataques** (`src/stego/attacks/image.py`): `jpeg(q, subsampling)`,
`crop(x, y, w, h)`, `rescale(long_side)`, `whatsapp(long_side=1600, quality=75)`.

**Coste medido:** marcado 0.2 s a 1024 px (3 s a 2400 px). Verificación 0.2 s con
escala 1.0; 1–3 s con búsqueda de escala a 1024 px, hasta 20 s a 2400 px. La
interfaz debe asumir latencia visible y no fingir que es instantánea.

**Recomendación operativa del repo:** normalizar a 1024 px antes de marcar. Es
más rápido y más fiable.

**Límites declarados (no ocultar en la interfaz):**

- Rotación y escalado no uniforme: no soportados.
- JPEG Q20: fuera de alcance en todos los perfiles probados.
- Recorte mínimo ~256 px de lado marcando a 1024 px.
- Reescalado por debajo de ×0.75: estado en revisión. `docs/resultados.md`
  registra ×0.5 como fallo abierto (0/4 en ambos perfiles); hay una corrección
  sin commitear en el árbol de trabajo que el usuario reporta como resuelta y que
  todavía no está reflejada en la documentación. **La interfaz debe mostrar lo
  que el benchmark devuelva en el momento, nunca un número escrito a mano.**
- **La ausencia de marca no prueba nada.** Puede ser un archivo ajeno o uno
  propio degradado.

## Brand Commitments

- **El producto se llama Stegora**, y el dominio ya está comprado. Escrito así:
  mayúscula inicial y nada más, nunca «STEGORA» ni «stegora» en prosa.
- El nombre del CLI sigue siendo `stego`. El remoto se llama `criptografia`; el
  directorio de trabajo, `mcic-trabajo-grado-1`. **Registro de procedencia** es el
  nombre de la herramienta dentro del producto, no del producto.
- **Regla de producto no negociable:** el veredicto nunca acusa. Los estados son
  «identificador recuperado» y «sin marca legible», jamás «es falso» o «no es
  tuyo». Está escrito como comentario en `src/stego/cli.py`.
- El idioma del producto es español.

## Evidence on Hand

Todo verificable dentro del repo, sin nada que inventar:

| Fuente | Qué aporta |
|---|---|
| `docs/resultados.md` | Tabla medida, metodología, coste, fallo abierto |
| `docs/auditoria.md` | Hallazgos C1–C9 del sistema anterior y cómo se corrigieron |
| `benchmarks/bench_image.py` | Regenera la tabla completa |
| `src/stego/attacks/image.py` | Batería de ataques de canal |
| `tools/whatsapp_test.py` | Prueba de extremo a extremo por canal real |
| `tests/` | `test_chaos`, `test_image_crop`, `test_image_jpeg`, `test_image_roundtrip`, `test_payload_ecc` |

| `web/tasas.json` | **Las únicas cifras vigentes del perfil de demo.** Lo produce `web/tasas.py` |

**Cifras vigentes vs. históricas.** El perfil de la demo se mide sobre **3
fotografías reales × 10 firmas = 30 intentos por ataque** (`web/tasas.json`):
Δ=26, `template_amp` 5.0 con enmascaramiento y `floor` 0.12, PSNR 39.27 dB; seis
ataques al 100 % y los dos recortes chicos al **97 %**, sin redondear. Las tablas
de `README.md` y `docs/resultados.md` son sobre **imágenes sintéticas** (lisa,
texturizada, oscura, alto contraste), se midieron antes del enmascaramiento
perceptual y están marcadas como pendientes de rehacer: valen como referencia
histórica, no como el comportamiento actual.

**Ausencias que no se pueden rellenar inventando:** el corpus fotográfico son
**tres fotografías**, no un corpus validado, y sus archivos no están en el repo,
así que la medición no es reproducible por un tercero tal cual. No hay clientes,
ni usuarios reales, ni entidades emisoras, ni despliegue, ni integración por API,
ni precios acordados. La rama de audio conserva todos los defectos auditados y
sus resultados no son válidos.

## Product Principles

1. **El veredicto nunca acusa.** «Recuperado» o «no puedo verificar». Nunca
   «falso».
2. **Los límites pesan lo mismo que los éxitos.** Lo que rompe la marca se
   muestra con la misma prominencia que lo que sobrevive.
3. **Recuperación exacta o fallo.** Ningún porcentaje de bits, en ninguna parte
   de la interfaz.
4. **Todo número visible tiene que ser reproducible** con un comando del repo. Si
   la interfaz lo muestra, es porque el códec lo acaba de calcular.
5. **La degradación se ve.** El jurado tiene que ver la imagen destrozada, no
   leer que fue destrozada.

## Accessibility & Inclusion

Requisito nacido de la escena, no genérico: **legibilidad de proyector**. Sala
iluminada, lectura a 5 metros, cañón con gama pobre y negros lavados. Exige
contraste alto, tipografía grande, y que ningún estado dependa solo del color
—cada resultado necesita también forma o texto. La interfaz se maneja con
teclado durante la demo: el operador no debe tener que apuntar con el mouse.
