# Resultados medidos

## Metodología

Cada fila es **recuperación exacta del identificador de 16 bytes**, no un
porcentaje de bits. El criterio es binario: o el tag AEAD valida y el
identificador coincide con el insertado, o cuenta como fallo.

Esto es deliberado. El sistema anterior declaraba éxito con ">95% de bits
correctos", lo que no significa recuperar nada: sin corrección de errores un
solo bit malo rompe el descifrado. Detalle en [auditoria.md](auditoria.md).

Cuatro tipos de contenido sintético (`benchmarks/bench_image.py`): liso,
texturizado, oscuro y de alto contraste. Reproducible con:

```bash
.venv/bin/python benchmarks/bench_image.py --size 1024x768
.venv/bin/python benchmarks/bench_image.py --size 1024x768 --delta 42
```

**Pendiente**: validación sobre fotografías reales. Los resultados de abajo son
sobre imágenes sintéticas con estadísticas variadas, no sobre un corpus
fotográfico.

> ⚠️ **Las tablas de esta página están pendientes de rehacer.** Se midieron
> **antes** del enmascaramiento perceptual de la plantilla (`image/masking.py`),
> que ahora va activo por defecto. Hay que volver a correr
> `benchmarks/bench_image.py` y reemplazarlas antes de citarlas en ninguna parte;
> mientras tanto valen como referencia histórica, no como el comportamiento
> actual. (La amplitud no las afecta: este banco usa el default del códec, 2.0,
> no el perfil de la demo.)
>
> **`web/tasas.json` ya se rehízo**, y esas sí son actuales: perfil de la demo
> `template_amp = 5.0` con enmascaramiento y `floor` 0.12, Δ=26, 3 fotografías ×
> 10 firmas = 30 intentos por ataque → **seis ataques al 100 %, los dos recortes
> chicos al 97 %, PSNR 39.27 dB**. Están en `web/README.md` junto con la medición
> que separa qué cuesta la amplitud, qué cuesta la máscara y qué cuesta el floor.
>
> El PSNR además se calculaba promediando **decibelios** en vez de MSE
> (`web/tasas.py`), lo que lo sesgaba hacia la peor imagen del lote. Corregido.

## Imágenes de 1024×768 (marcadas a su resolución nativa)

Ésta es la configuración recomendada en producción: normalizar a 1024 px antes
de marcar.

| Ataque | Δ = 26 (PSNR 42.3 dB) | Δ = 42 (PSNR 39.0 dB) |
|---|---|---|
| Sin ataque | 4/4 | 4/4 |
| JPEG Q90 | 4/4 | 4/4 |
| JPEG Q75 | 4/4 | 4/4 |
| JPEG Q50 | 4/4 | 4/4 |
| JPEG Q30 | 1/4 | **4/4** |
| Recorte 800×600 @(13,37) | 4/4 | 4/4 |
| Recorte 800×600 + JPEG Q75 | 4/4 | 4/4 |
| Recorte 400×300 + JPEG Q75 | 4/4 | 4/4 |
| Recorte 256×256 + JPEG Q75 | 4/4 | 4/4 |
| Reescalado ×0.75 + JPEG Q75 | 4/4 | 4/4 |
| Reescalado ×0.5 + JPEG Q75 | 1/4 | 4/4 |
| Canal WhatsApp simulado (1600 px / Q75 / 4:2:0) | 4/4 | 4/4 |
| Recorte grande + canal simulado | 4/4 | 4/4 |

**Totales**: Δ=26 → 46/52 recuperaciones exactas; **Δ=42 → 52/52**. Los 6 fallos
del perfil estándar son los 3 de JPEG Q30 y los 3 de ×0.5; el perfil robusto no
falla ninguno.

Falsos positivos con passphrase incorrecta: **0 de 8 intentos** en ambos
perfiles. Es el número que no puede fallar nunca: un identificador inventado
sería peor que no encontrar nada.

## Imágenes grandes marcadas sin normalizar

A 2400×1800 con `base_long = 1024` (el residuo se interpola al tamaño nativo):

| Ataque | Resultado |
|---|---|
| Sin ataque, JPEG Q90–Q30, ×0.75, canal simulado | recupera en 3 de 4 contenidos |
| Recorte 800×600 | recupera en 3 de 4 contenidos |
| Recorte 256×256 | **no recupera**: a esa escala el recorte no llega a contener una tesela completa |

El contenido que falla es un tablero de ajedrez sintético de periodo perfecto,
que desvía el buscador de escala hacia la periodicidad de la propia imagen.

**Conclusión operativa**: normalizar a 1024 px antes de marcar no es solo más
rápido (0.2 s frente a 2–20 s por verificación), también es más fiable.

## Coste

| Operación | 1024 px | 2400 px |
|---|---|---|
| Marcado | 0.2 s | 3 s |
| Verificación con escala 1.0 | 0.2 s | 0.3 s |
| Verificación con búsqueda de escala | 1–3 s | 2–20 s |

## Reescalado ×0.5: causa y solución

Durante el desarrollo, `reescalado ×0.5 + Q75` fallaba en los cuatro contenidos y
en ambos perfiles. El primer diagnóstico —"pérdida de información"— era **falso**.

Los portadores tienen periodo de 16 px; tras reducir a la mitad quedan en 8 px,
muy por encima del límite de Nyquist de 2 px. La información seguía ahí, y la
búsqueda de escala incluso encontraba el factor correcto (1.99 frente a 2.00).

La causa real, medida: **el QIM es frágil al escalado de amplitud**. El ciclo
reducir–recomprimir–ampliar atenúa los coeficientes portadores:

| Contenido | Ganancia del portador | Residuo |
|---|---|---|
| liso | 0.745 | σ = 4.50 |
| texturizado | 0.995 | σ = 9.62 |

Con ganancia 0.745 la retícula del cuantizador queda desplazada y
`round(2(c−d)/Δ) mod 2` da mal aunque el coeficiente conserve toda su
información.

**Solución implementada**: búsqueda de ganancia (`_refine_gain`). Barre la
ganancia en dos pasadas —gruesa de 0.60 a 1.40 en pasos de 0.05, fina de ±0.05 en
pasos de 0.005— y decide por BER de pilotos. La ganancia solo afecta a los
valores blandos, así que la DCT se calcula una sola vez y el barrido es puro
`_accumulate`: recalcularla por candidata costaba dos órdenes de magnitud más.

Resultado: `×0.5` pasa a 4/4 con Δ=42, y la ganancia hallada (0.800) coincide con
la medida (0.745). Con Δ=26 solo recupera 1/4, porque el residuo del ciclo
(σ ≈ 4.5) es demasiado grande frente a Δ/4 = 6.5; con Δ=42 el margen se duplica.

De paso, la compensación de ganancia cubre los cambios moderados de brillo y
contraste, que antes tampoco estaban soportados.

## Coste de la verificación

Medido sobre una imagen de 1024×768:

| Caso | Tiempo |
|---|---|
| Correcto, sin ataque | 0.27 s |
| Correcto, JPEG Q75 | 0.31 s |
| Correcto, recorte 800×600 + Q75 | 0.20 s |
| Correcto, reescalado ×0.5 + Q75 | 1.72 s |
| Llave incorrecta | 7.4 s |
| Imagen sin marcar | 8.6 s |

El camino rápido —probar la escala 1.0 antes de buscar— es lo que mantiene el
caso común por debajo del medio segundo: la mayoría de los archivos llegan a su
resolución de marcado y no hace falta buscar nada.

Los casos negativos cuestan más porque el decodificador agota la búsqueda antes
de rendirse. El barrido exhaustivo de escalas (`deep`) está **desactivado por
defecto**: cuesta ~90 s y solo ayuda cuando la imagen tiene estructura periódica
fuerte que desvía la sincronía. Sin él, un archivo ajeno se descarta en segundos.

Una advertencia sobre el BER de pilotos como criterio: el valor que se compara es
el *mínimo* sobre muchos intentos de alineación, y con 96 pilotos ese mínimo baja
hasta ~0.31 por puro azar sobre miles de intentos. Por eso un umbral sobre él no
basta como única defensa, y el criterio de aceptación final sigue siendo el tag
AEAD.


## Integridad por región

Misma marca, leída por celdas de 32 px. Imágenes de 640×512 y 1024×768,
perfil Δ=42.

| Operación | 640×512 | 1024×768 |
|---|---|---|
| Sin tocar | limpia | limpia |
| JPEG Q75 | limpia | limpia |
| JPEG Q30 | limpia | limpia |
| Canal WhatsApp | limpia | limpia |
| Brillo +20% | limpia | limpia |
| Contraste +30% | limpia | limpia |
| Recorte 400×300 | limpia | limpia |
| **Pegar un objeto (220×180 px)** | **alterada, 30 celdas** | **alterada, 33 celdas** |
| **Desenfocar una zona (300×250 px)** | **alterada, 80 celdas** | **alterada, 59 celdas** |
| Poner texto (~13×100 px) | no detectada | alterada, 1 celda |

Cero falsas alarmas en todo lo que hace un canal. Las celdas marcadas caen dentro
de la región editada, no repartidas por la imagen.

**El límite es la resolución de celda**: un texto sobreimpreso de 13×100 px está
en el borde de lo detectable y se pierde en la imagen más chica. Bajar
`--cell-blocks` mejora la sensibilidad a costa de más falsas alarmas.

Y el límite conceptual, que es más importante: esto detecta **edición local**. Un
reencuadre, un filtro global o un cambio de color afectan la imagen entera de
forma uniforme y no se distinguen de un canal. No es un detector de manipulación
universal.
