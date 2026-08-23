# El bucket de estado tiene que existir antes del primer `init`, así que se crea
# a mano una sola vez:
#
#   aws s3api create-bucket --bucket stego-tfstate --region us-east-1
#   aws s3api put-bucket-versioning --bucket criptoaudio-tfstate \
#     --versioning-configuration Status=Enabled
#
# Después se descomenta este bloque y se ejecuta `terraform init -migrate-state`.
# Desde Terraform 1.10 el bloqueo es nativo con use_lockfile: no hace falta
# ninguna tabla de DynamoDB.

# terraform {
#   backend "s3" {
#     bucket       = "stego-tfstate"
#     key          = "criptoaudio/terraform.tfstate"
#     region       = "us-east-1"
#     encrypt      = true
#     use_lockfile = true
#   }
# }
