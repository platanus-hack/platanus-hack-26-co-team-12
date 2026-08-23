#!/usr/bin/env bash
# Despliega a produccion. Desde la raiz del repositorio:
#
#   scripts/deploy.sh          front y back
#   scripts/deploy.sh front    solo la interfaz
#   scripts/deploy.sh back     solo la Lambda
#
# El estado de terraform es local, asi que vive en el directorio donde se hizo
# el apply, que no tiene por que ser este checkout. TF_DIR apunta a ese
# directorio; por defecto se usa el ./terraform de aqui:
#
#   TF_DIR=~/ruta/al/otro/terraform scripts/deploy.sh
#
set -euo pipefail

QUE="${1:-todo}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# Ajustes de esta maquina (TF_DIR, sobre todo). No se versiona: cada uno tiene
# el estado en un sitio distinto. Lo que venga del entorno tiene prioridad.
[ -f .deploy.env ] && . ./.deploy.env

# --- credenciales ----------------------------------------------------------
# Las AWS_* de una sesion anterior tienen prioridad sobre todo lo demas, asi que
# si estan caducadas la propia CLI las relee y "refresca" a si mismas. Hay que
# borrarlas antes de pedir las nuevas.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN \
      AWS_CREDENTIAL_EXPIRATION AWS_SECURITY_TOKEN
eval "$(aws configure export-credentials --format env)"

REGION="${AWS_REGION:-us-east-1}"
TF_DIR="${TF_DIR:-$RAIZ/terraform}"

[ -d "$TF_DIR" ] || { echo "TF_DIR no es un directorio: $TF_DIR" >&2; exit 1; }
cd "$TF_DIR"

# Sobre un estado vacio `terraform output` no falla: escribe el aviso "No
# outputs found" por stdout y devuelve 0, asi que la variable acaba con el
# texto del warning dentro y el error solo aparece mucho despues (docker login
# quejandose de una URL con caracteres de control). Comprobamos el estado antes
# y validamos cada valor.
if ! terraform state list >/dev/null 2>&1; then
  echo "terraform no tiene estado en $(pwd)." >&2
  echo "El estado es local y vive donde hiciste el apply. Apunta ahi con TF_DIR:" >&2
  echo "  TF_DIR=~/ruta/al/otro/terraform $0 $QUE" >&2
  exit 1
fi

# Un valor valido es una sola linea sin espacios ni escapes ANSI.
tfout() {
  local v
  v=$(terraform output -raw "$1" 2>/dev/null)
  case "$v" in
    ''|*[!a-zA-Z0-9.:/_-]*)
      echo "el output '$1' esta vacio o no es valido; corre 'terraform apply' primero." >&2
      return 1 ;;
  esac
  printf '%s' "$v"
}

REPO=$(tfout ecr_repository_url)
BUCKET=$(tfout bucket_front)
DIST=$(tfout distribution_id)
URL=$(tfout url)
cd "$RAIZ"

echo "→ repo   $REPO"
echo "→ bucket $BUCKET"
echo "→ cdn    $DIST"
echo

# --- back ------------------------------------------------------------------
if [ "$QUE" = "todo" ] || [ "$QUE" = "back" ]; then
  echo "== Construyendo la imagen =="
  aws ecr get-login-password --region "$REGION" \
    | docker login --username AWS --password-stdin "${REPO%%/*}" >/dev/null

  # --network=host: el DNS de los contenedores no resuelve en esta maquina.
  # --provenance/--sbom false y --platform: sin ellos buildx genera un manifest
  # list con atestaciones, y Lambda solo acepta manifiesto unico.
  docker build --network=host --target lambda \
    --provenance=false --sbom=false --platform linux/amd64 \
    -t "${REPO}:latest" .

  docker push "${REPO}:latest"

  # Terraform no se entera de que la imagen cambio si la etiqueta sigue siendo
  # "latest": hay que decirselo a Lambda directamente.
  echo "== Actualizando la Lambda =="
  aws lambda update-function-code --function-name stego \
    --image-uri "${REPO}:latest" --output text --query LastUpdateStatus
  aws lambda wait function-updated --function-name stego
  echo "   lista"
fi

# --- front -----------------------------------------------------------------
if [ "$QUE" = "todo" ] || [ "$QUE" = "front" ]; then
  echo "== Subiendo la interfaz =="
  # index.html va en la raiz porque es el default_root_object de CloudFront,
  # y los assets bajo static/ porque es la ruta que pide el propio html.
  aws s3 cp web/static/index.html "s3://${BUCKET}/index.html" --only-show-errors
  aws s3 sync web/static "s3://${BUCKET}/static/" --delete --only-show-errors

  echo "== Invalidando la cache =="
  aws cloudfront create-invalidation --distribution-id "$DIST" \
    --paths '/*' --output text --query Invalidation.Status
fi

echo
echo "Listo. $URL"
echo "La invalidacion de CloudFront tarda un par de minutos en propagar."
