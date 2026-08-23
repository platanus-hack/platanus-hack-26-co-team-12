# Stegora — team-12 · Platanus Hack 26: Bogotá

<img src="./project-logo.png" alt="Stegora" width="200" />

Track: 🛡️ AI Security

- **Demo en vivo:** <https://stegora.xyz/>
- **Repositorio:** <https://github.com/platanus-hack/platanus-hack-26-co-team-12>

Marca de procedencia que vive **dentro de los píxeles**. El emisor firma una
imagen y recibe un archivo visualmente idéntico (PSNR 39.27 dB); después, aunque
la imagen llegue recortada, reescalada, recomprimida o reenviada por WhatsApp, el
identificador de 16 bytes se recupera exacto. Es un **registro, no un detector**:
devuelve «identificador recuperado» o «sin marca legible», nunca una acusación.

Responde al Artículo 50 del AI Act, donde el marcado por metadatos (C2PA) se
destruye en el primer reenvío.

La marca vive en las **frecuencias**, no en los bits sueltos: es lo que un
compresor con pérdida tiene que respetar, y por eso el mismo mecanismo traslada a
audio y video. Hoy solo la rama de imagen está medida y es la que se demuestra;
la rama de audio del repo es anterior y la auditoría interna la dejó marcada como
no válida (`docs/auditoria.md`).

## Resultados

30 intentos por ataque (3 fotografías × 10 firmas), `web/tasas.json`:

| Ataque | Recuperación |
|---|---|
| Limpia · JPEG Q75 · recorte 800 px · escala ×0.75 · WhatsApp · recorte+WhatsApp | 100 % |
| Recorte a 400 px · recorte a 256 px | 97 % |

Falsos positivos con passphrase incorrecta: 0. Límites declarados: rotación no
soportada, JPEG Q20 fuera de alcance, recorte mínimo ~256 px marcando a 1024 px.

## Correr local

```bash
scripts/install.sh
.venv/bin/python -m uvicorn web.server:app --port 8000   # http://localhost:8000
```

O con Docker: `docker compose up` → <http://localhost:8080>.

## Mapa del repo

| Ruta | Qué hay |
|---|---|
| `src/stego/` | Códec: DCT+QIM, ChaCha20-Poly1305, Reed–Solomon, batería de ataques |
| `web/` | Demo: FastAPI + HTML/CSS/JS plano, sin build step |
| `benchmarks/`, `docs/resultados.md` | Medición y metodología |
| `terraform/`, `scripts/deploy.sh` | Despliegue en AWS (CloudFront + S3 + Lambda, CI por OIDC) |
| `deck/` | Deck de la presentación |
| `PRODUCT.md`, `DESIGN.md` | Decisiones de producto y de interfaz |

## Equipo

- Daniel Andrés Moreno Cruz ([@alinedmooner](https://github.com/alinedmooner))
- Brayan Elian Peña Jaimes ([@darkelian](https://github.com/darkelian))
- Carlos Mora ([@fozzy3](https://github.com/fozzy3))
- Brayan Alejandro Riveros ([@brayan-22](https://github.com/brayan-22))
- Cristian Stiven Guzman Tovar ([@cristiangt089](https://github.com/cristiangt089))
