# Estado de los hallazgos de auditoría

Los resultados de robustez publicados en `results.txt` y
`resultados-mtericas-ataques.txt` (rama de audio) **no son válidos**. La causa
raíz está identificada y verificada; abajo, qué se corrigió en el codec nuevo y
qué sigue pendiente en el código de audio original.

## Corregido en `src/stego/`

| # | Hallazgo | Corrección |
|---|---|---|
| C1 | El modo "aleatorio" era idéntico al secuencial: el bucle indexaba con `i` y `bit_index` solo se usaba para leer una longitud | El *layout* completo (dither, roles, pilotos, plantilla) deriva del caos y se indexa por posición de tesela. `tests/test_chaos.py` |
| C2 | `generar_secuencia_aleatoria` no terminaba para n ≥ 20 834 (muestreo con rechazo; el bin 0 nunca salía con r < 4) | Fisher–Yates O(n) en `chaos.chaos_permutation`. Probado con n = 50 000 |
| C3 | No existía llave: `X0/R/N_WARMUP` eran constantes públicas del repo | `keys.derive`: passphrase → Argon2id → HKDF → (k_cipher, k_chaos) |
| C4 | Two-time pad: el mismo keystream cifraba todos los mensajes; sin nonce ni MAC | ChaCha20-Poly1305 con nonce por mensaje y cabecera como AAD |
| C5 | Generador roto aunque x0 fuese secreto: predecible, ciclos cortos, sesgo monobit z = +10.5 por r = 3.999952, no determinista entre plataformas | Punto fijo de 64 bits con **r = 4 exacto** y resiembra HKDF. Test monobit en verde; determinista por construcción |
| C7 | PSNR y MSE desbordaban en int16 (`32767**2` ≡ 1 mod 2¹⁶) | Métricas en float64 con MAX según el tipo del cover |
| C8 | El pipeline nunca se validaba de extremo a extremo; el receptor necesitaba un sidecar con inicio, fin, longitud y modo | La trama se describe a sí misma (cabecera + nonce + AEAD) y la sincronía es ciega. Sin sidecar, sin llave en disco |
| C9 | La "compresión" era LLMLingua + gemma3:27b: con pérdida, no determinista, 99.4% del tiempo total | `zlib`: sin pérdida, microsegundos. La compresión semántica queda como extra opcional |
| A.2 | `ord(char)` → uint8 reventaba con cualquier carácter > U+00FF | El payload es binario; el texto viaja en UTF-8 |

## Cómo se evita repetir C6

C6 —la batería de ataques medía 22 050 muestras de silencio digital por rebanar
un array 2D con índices calculados sobre el 1D— es el hallazgo más grave, porque
convirtió "0 de 18 ataques superados" en un "11 de 18" publicado.

Dos decisiones del banco nuevo lo hacen imposible:

1. **Se evalúa contra el identificador realmente insertado**, no contra los LSB
   del propio estego. Si la extracción devuelve otra cosa, es un fallo.
2. **El criterio es la recuperación exacta del payload**, no un porcentaje de
   bits por encima de un umbral. Un ">95% de bits correctos" no es recuperar
   nada: sin corrección de errores, un solo bit malo rompe el descifrado.

## Pendiente

- La rama de audio (`src/compresion`, `src/encriptado`, `src/esteganografiado`,
  `src/utils`, `src/api`) **sigue con todos los defectos auditados**. El LSB
  temporal no sobrevive a ningún ataque que altere ±1 LSB; migrarlo a QIM sobre
  MDCT es trabajo aparte.
- La API (`src/api/app.py`) conserva el DoS de un solo paquete, el bloqueo del
  event loop, la llave en disco y el CORS permisivo. No debe exponerse.
