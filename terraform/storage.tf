data "aws_caller_identity" "actual" {}

locals {
  # Los nombres de bucket son globales, así que se sufijan con la cuenta.
  sufijo       = data.aws_caller_identity.actual.account_id
  bucket_front = "${var.project}-front-${local.sufijo}"
  bucket_media = "${var.project}-estado-${local.sufijo}"
  usa_dominio  = var.domain_name != ""
}

# ---------------------------------------------------------------------------
# Bucket del front: html, css y js. Privado; solo lo lee CloudFront.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "front" {
  bucket = local.bucket_front
}

resource "aws_s3_bucket_public_access_block" "front" {
  bucket                  = aws_s3_bucket.front.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "front" {
  bucket = aws_s3_bucket.front.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ---------------------------------------------------------------------------
# Bucket de estado: el registro de emisores (registro.json). En Lambda el
# disco es de solo lectura salvo /tmp, asi que el registro vive aqui.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket" "media" {
  bucket = local.bucket_media
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# El registro es el unico estado del sistema: con versionado, un despliegue
# equivocado no lo pierde para siempre.
resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Las sesiones del cotejo guardan la imagen marcada (unos 2 MB cada una) y solo
# sirven mientras dura una demo. El registro, en cambio, no caduca.
resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket = aws_s3_bucket.media.id

  rule {
    id     = "caducar-sesiones"
    status = "Enabled"

    filter {
      prefix = "sesiones/"
    }

    expiration {
      days = 1
    }
  }
}
