variable "project" {
  description = "Prefijo de todos los nombres de recurso."
  type        = string
  default     = "stego"
}

variable "region" {
  description = "Región donde vive todo salvo el certificado de CloudFront."
  type        = string
  default     = "us-east-1"
}

variable "domain_name" {
  description = <<-EOT
    Dominio propio, por ejemplo "criptoaudio.ejemplo.com".
    Si se deja vacío no se crean ni el certificado ni los registros DNS, y el
    sitio se sirve por el dominio que asigna CloudFront.
  EOT
  type        = string
  default     = ""
}

variable "hosted_zone_id" {
  description = "Zona alojada de Route53 donde crear los registros. Obligatorio si domain_name no está vacío."
  type        = string
  default     = ""
}

variable "image_tag" {
  description = "Etiqueta de la imagen en ECR. La imagen debe existir antes del primer apply."
  type        = string
  default     = "latest"
}

variable "lambda_memory_mb" {
  description = "Memoria de la Lambda. El codec es numpy/scipy sobre imagenes."
  type        = number
  default     = 2048
}

variable "registro_passphrase" {
  description = "Passphrase de la que se derivan las llaves de los emisores (STEGO_REGISTRO)."
  type        = string
  sensitive   = true
}

variable "github_repo" {
  description = "Repositorio autorizado a desplegar vía OIDC, en formato owner/repo. Vacío desactiva el rol de CI."
  type        = string
  default     = "platanus-hack/platanus-hack-26-co-team-12"
}
