#!/bin/bash
# Instala el codec de imagen en un entorno virtual.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev,web]"
echo
echo "Listo. Uso:"
echo "  .venv/bin/python -m stego.cli embed   --in foto.jpg --out marcada.png --passphrase '...'"
echo "  .venv/bin/python -m stego.cli verify  --in recibida.jpg --passphrase '...'"
echo "  .venv/bin/python -m uvicorn web.server:app --port 8000     # demo web"
