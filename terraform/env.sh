# Prepara el entorno para terraform. Uso:
#
#   source env.sh
#
# Hace dos cosas:
#
#  1. Exporta las credenciales de AWS. Tu ~/.aws/config usa `login_session`,
#     que es un mecanismo de la CLI v2 que el SDK de Terraform no lee. Este
#     comando las traduce a variables de entorno, que si entiende. Caducan:
#     si terraform vuelve a decir "No valid credential sources found", repite
#     el source.
#
#  2. Carga la passphrase del registro desde .secrets, generandola la primera
#     vez. No se regenera nunca: de ella se derivan las llaves de todos los
#     emisores, y si cambia, lo ya firmado deja de verificarse.

# Las AWS_* de una sesion anterior tienen prioridad sobre todo lo demas, asi
# que si estan caducadas la propia CLI las relee y "refresca" a si mismas:
# "Credentials were refreshed, but the refreshed credentials are still
# expired". Hay que borrarlas antes de pedir las nuevas.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN       AWS_CREDENTIAL_EXPIRATION AWS_SECURITY_TOKEN

eval "$(aws configure export-credentials --format env)" || {
  echo "No se pudieron exportar las credenciales. Sesion de 'aws login' caducada?" >&2
  return 1 2>/dev/null || exit 1
}

_secretos="$(pwd)/.secrets"

if [ ! -f "$_secretos" ]; then
  umask 077
  printf 'TF_VAR_registro_passphrase=%s\n' "$(openssl rand -base64 32)" > "$_secretos"
  echo "Passphrase generada en $_secretos - guardala en tu gestor de contrasenas."
fi

set -a
. "$_secretos"
set +a
unset _secretos

echo "Listo: cuenta $(aws sts get-caller-identity --query Account --output text)"
echo "Las credenciales caducan a las ${AWS_CREDENTIAL_EXPIRATION:-?}"
