# Stegora

**La firma de quién hizo el archivo va adentro del archivo, no en una etiqueta
que se borra al compartirlo.**

🔗 <https://stegora.xyz/> · Track: 🛡️ AI Security

## El problema

Cualquiera puede fabricar hoy una foto, un audio o un video que parezca real. El
problema de fondo no es ese: es que ya no se puede **probar de dónde salió el
material auténtico**.

El Artículo 50 del AI Act exige marcar el contenido generado o distribuido por
sistemas de IA. El mecanismo mayoritario para cumplirlo —C2PA / Content
Credentials— escribe esa marca en los **metadatos**: una etiqueta pegada por
fuera del archivo. Los metadatos se borran en el primer reenvío —una subida a una red
social, un mensaje de WhatsApp—. El archivo sigue
circulando; la procedencia, no.

## Qué hace Stegora

Pone la marca **adentro**, en los coeficientes DCT de la propia imagen:

1. **Registrar.** El emisor firma una imagen y recibe un archivo visualmente
   idéntico —PSNR medio de **39.27 dB**— con un identificador de 16 bytes
   incrustado en los píxeles.
2. **Verificar.** Cualquiera sube esa imagen, por maltratada que llegue, y
   Stegora devuelve quién la emitió y cuándo, o dice que no encuentra marca
   legible.

**Es un registro, no un detector.** Un detector estima a posteriori y se equivoca
en las dos direcciones; esto anota en el momento cero y comprueba después. El
criterio de aceptación es el tag AEAD, con probabilidad de falso positivo
**2⁻¹²⁸**: el identificador se recupera exacto o no se recupera —no existe el
«95 % de los bits».

**El veredicto nunca acusa.** Los dos estados son «identificador recuperado» y
«sin marca legible». La ausencia de marca no prueba nada: puede ser un archivo
ajeno o uno propio degradado más allá del límite.

## Resultados medidos

Perfil de la demo: 3 fotografías reales × 10 firmas = **30 intentos por ataque**
(`web/tasas.json`, regenerable con `web/tasas.py`).

| Ataque de canal | Recuperación exacta |
|---|---|
| Imagen limpia | 100 % (30/30) |
| JPEG Q75 | 100 % (30/30) |
| Recorte a 800 px | 100 % (30/30) |
| Recorte a 400 px | 97 % (29/30) |
| Recorte a 256 px | 97 % (29/30) |
| Reescalado ×0.75 | 100 % (30/30) |
| WhatsApp (1600 px, Q75) | 100 % (30/30) |
| Recorte + WhatsApp | 100 % (30/30) |

Falsos positivos con passphrase incorrecta: **0**.

## Límites, declarados

Pesan lo mismo que los éxitos, y por eso están en la interfaz y no en una nota al
pie:

- Rotación y escalado no uniforme: **no soportados**.
- JPEG Q20: **fuera de alcance** en todos los perfiles probados.
- Recorte mínimo de **~256 px** de lado marcando a 1024 px.
- Reescalado por debajo de ×0.75: en revisión.
- El corpus son **tres fotografías**, no un corpus validado.

## Cómo funciona

`id de 16 B → zlib → ChaCha20-Poly1305 → Reed–Solomon(84,44) → QIM sobre DCT 8×8
→ tesela de 128 px repetida + plantilla de sincronía aditiva`. Las llaves salen
de una passphrase por Argon2id → HKDF, separadas en `k_cipher` (por tenant) y
`k_chaos` (compartida): un verificador revisa N clientes pagando **una sola
búsqueda de sincronía**, y ningún cliente puede leer ni falsificar las marcas de
otro.

El payload son 16 bytes **aleatorios**, nunca datos reales: meter datos personales
dentro del archivo convertiría un producto de cumplimiento en un incumplimiento
de protección de datos.

Marcado: 0.2 s a 1024 px. Verificación: 0.2 s con escala conocida, 1–3 s con
búsqueda de escala.

## Imagen hoy, audio y video después

La marca no se esconde en los bits sueltos —eso es lo que hace el LSB clásico, y
muere con la primera recompresión— sino en las **frecuencias** del archivo, que es
justo lo que un compresor con pérdida tiene que respetar para que el resultado
siga viéndose (o sonando) bien. Por esa razón sobrevive a un JPEG, y por esa misma
razón el mecanismo traslada a audio y a video.

Está enunciado como lo que es, un siguiente paso y no una capacidad actual: **hoy
solo la rama de imagen está medida y es la que se demuestra**. El repo conserva
una rama de audio anterior basada en LSB temporal que la auditoría interna dejó
marcada como no válida (`docs/auditoria.md`); migrarla a QIM sobre MDCT es el
trabajo pendiente, y hasta que esté medida no se presenta como funcionando.

## Para qué sirve

- **Trazabilidad de fugas.** Cada descarga sale marcada con el identificador de
  quien la bajó; si el archivo aparece afuera, se sabe de dónde salió.
- **Contenido subido a plataforma.** Lo que un usuario sube queda marcado con su
  identificador y la fecha. Los logs se cuestionan; el archivo no.
- **Detección de edición local.** El cotejo por región compara la marca celda a
  celda y señala dónde no coincide, desde ~160 px de lado. Detecta edición local
  con ese piso medido; nunca prueba que una imagen *no* fue manipulada.

## Stack

Códec en Python puro (numpy / scipy / pillow) sobre FastAPI, front en HTML/CSS/JS
plano sin build step. Desplegado en AWS con Terraform: CloudFront + S3 + Lambda,
CI por OIDC sin claves guardadas.

## Equipo — team-12 · Bogotá

Daniel Andrés Moreno Cruz ([@alinedmooner](https://github.com/alinedmooner)) ·
Brayan Elian Peña Jaimes ([@darkelian](https://github.com/darkelian)) ·
Carlos Mora ([@fozzy3](https://github.com/fozzy3)) ·
Brayan Alejandro Riveros ([@brayan-22](https://github.com/brayan-22)) ·
Cristian Stiven Guzman Tovar ([@cristiangt089](https://github.com/cristiangt089))
