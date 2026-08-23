# Imagen de la demo web. El códec es Python puro sobre numpy/scipy/pillow, así
# que no hace falta ninguna biblioteca del sistema.
#
#   docker build --target local  -t stego:local .
#   docker build --target lambda -t stego:lambda .

FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY pyproject.toml README.md ./
COPY src ./src

# El códec y la demo web salen del mismo pyproject: el extra [web] añade
# fastapi, uvicorn y python-multipart sobre las cinco del núcleo. Declaradas en
# un solo sitio: repetirlas aquí las dejaba derivar (había tres pines distintos
# de uvicorn en el repo).
RUN pip install ".[web]"

COPY web ./web


# --------------------------------------------------------------------------
# Desarrollo: uvicorn sirviendo también el front, como en local.
# --------------------------------------------------------------------------
FROM base AS local

EXPOSE 8000
CMD ["uvicorn", "web.server:app", "--host", "0.0.0.0", "--port", "8000"]


# --------------------------------------------------------------------------
# Lambda: el mismo código invocado por el runtime.
# Requiere que web/server.py termine con:  handler = Mangum(app)
# --------------------------------------------------------------------------
FROM base AS lambda

RUN pip install awslambdaric mangum boto3

ENTRYPOINT ["python", "-m", "awslambdaric"]
CMD ["web.server.handler"]
