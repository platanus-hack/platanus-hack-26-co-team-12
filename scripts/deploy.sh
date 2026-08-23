#!/usr/bin/env bash
# Despliega a produccion. Desde la raiz del repositorio:
#
#   scripts/deploy.sh          front y back
#   scripts/deploy.sh front    solo la interfaz
#   scripts/deploy.sh back     solo la Lambda
#
set -euo pipefail

QUE="${1:-todo}"
RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$RAIZ"

# --- credenciales ----------------------------------------------------------
# Las AWS_* de una sesion anterior tienen prioridad sobre todo lo demas, asi que
# si estan caducadas la propia CLI las relee y "refresca" a si mismas. Hay que
# borrarlas antes de pedir las nuevas.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN \
      AWS_CREDENTIAL_EXPIRATION AWS_SECURITY_TOKEN
eval "$(aws configure export-credentials --format env)"

REGION="${AWS_REGION:-us-east-1}"
cd terraform
REPO=$(terraform output -raw ecr_repository_url)
BUCKET=$(terraform output -raw bucket_front)
DIST=$(terraform output -raw distribution_id)
URL=$(terraform output -raw url)
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
