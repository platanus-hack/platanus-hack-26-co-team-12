data "aws_cloudfront_cache_policy" "optimizada" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "sin_cache" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "todo_menos_host" {
  name = "Managed-AllViewerExceptHostHeader"
}

# ---------------------------------------------------------------------------
# Zona DNS. Si no le pasas un hosted_zone_id, Terraform la crea: entonces hay
# que apuntar los nameservers del registrador a los que salen en el output
# "nameservers", o la validacion del certificado no termina nunca.
# ---------------------------------------------------------------------------

resource "aws_route53_zone" "web" {
  count = local.usa_dominio && var.hosted_zone_id == "" ? 1 : 0

  name = var.domain_name
}

locals {
  zone_id = local.usa_dominio ? (
    var.hosted_zone_id != "" ? var.hosted_zone_id : aws_route53_zone.web[0].zone_id
  ) : ""
}

# ---------------------------------------------------------------------------
# Certificado. Solo si hay dominio propio; si no, CloudFront sirve por su
# propio dominio con HTTPS incluido.
# ---------------------------------------------------------------------------

resource "aws_acm_certificate" "web" {
  count = local.usa_dominio ? 1 : 0

  provider          = aws.us_east_1
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# Registros que prueban a ACM que el dominio es tuyo.
resource "aws_route53_record" "validacion" {
  for_each = local.usa_dominio ? {
    for o in aws_acm_certificate.web[0].domain_validation_options :
    o.domain_name => {
      name   = o.resource_record_name
      record = o.resource_record_value
      type   = o.resource_record_type
    }
  } : {}

  zone_id         = local.zone_id
  name            = each.value.name
  type            = each.value.type
  records         = [each.value.record]
  ttl             = 60
  allow_overwrite = true
}

resource "aws_acm_certificate_validation" "web" {
  count = local.usa_dominio ? 1 : 0

  provider                = aws.us_east_1
  certificate_arn         = aws_acm_certificate.web[0].arn
  validation_record_fqdns = [for r in aws_route53_record.validacion : r.fqdn]
}

# ---------------------------------------------------------------------------
# Accesos de origen: los buckets siguen privados y la Function URL solo acepta
# peticiones firmadas por esta distribución.
# ---------------------------------------------------------------------------

resource "aws_cloudfront_origin_access_control" "front" {
  name                              = "${var.project}-front"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ---------------------------------------------------------------------------
# La distribución. Tres orígenes bajo un mismo dominio, que es lo que evita
# tener que configurar CORS entre el front y la API.
# ---------------------------------------------------------------------------

resource "aws_cloudfront_distribution" "web" {
  enabled             = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"
  aliases             = local.usa_dominio ? [var.domain_name] : []

  origin {
    origin_id                = "front"
    domain_name              = aws_s3_bucket.front.bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.front.id
  }

  origin {
    origin_id   = "api"
    domain_name = "${aws_apigatewayv2_api.api.id}.execute-api.${var.region}.amazonaws.com"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "https-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  # Por defecto, el front estático.
  default_cache_behavior {
    target_origin_id       = "front"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimizada.id
    compress               = true
  }

  # Toda la API cuelga de /api/. Sin cache: cada respuesta es distinta.
  dynamic "ordered_cache_behavior" {
    for_each = toset(["/api/*"])

    content {
      path_pattern             = ordered_cache_behavior.value
      target_origin_id         = "api"
      viewer_protocol_policy   = "redirect-to-https"
      allowed_methods          = ["GET", "HEAD", "OPTIONS", "PUT", "POST", "PATCH", "DELETE"]
      cached_methods           = ["GET", "HEAD"]
      cache_policy_id          = data.aws_cloudfront_cache_policy.sin_cache.id
      origin_request_policy_id = data.aws_cloudfront_origin_request_policy.todo_menos_host.id
      compress                 = true
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = local.usa_dominio ? null : true
    acm_certificate_arn            = local.usa_dominio ? aws_acm_certificate_validation.web[0].certificate_arn : null
    ssl_support_method             = local.usa_dominio ? "sni-only" : null
    minimum_protocol_version       = local.usa_dominio ? "TLSv1.2_2021" : null
  }
}

# ---------------------------------------------------------------------------
# Políticas de bucket: solo esta distribución puede leerlos.
# ---------------------------------------------------------------------------

resource "aws_s3_bucket_policy" "front" {
  bucket = aws_s3_bucket.front.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "cloudfront.amazonaws.com" }
      Action    = "s3:GetObject"
      Resource  = "${aws_s3_bucket.front.arn}/*"
      Condition = {
        StringEquals = {
          "AWS:SourceArn" = aws_cloudfront_distribution.web.arn
        }
      }
    }]
  })
}


# ---------------------------------------------------------------------------
# El alias que apunta el dominio a la distribución.
# ---------------------------------------------------------------------------

resource "aws_route53_record" "alias" {
  for_each = local.usa_dominio ? toset(["A", "AAAA"]) : toset([])

  zone_id = local.zone_id
  name    = var.domain_name
  type    = each.value

  alias {
    name                   = aws_cloudfront_distribution.web.domain_name
    zone_id                = aws_cloudfront_distribution.web.hosted_zone_id
    evaluate_target_health = false
  }
}
