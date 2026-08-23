# ---------------------------------------------------------------------------
# Registro de la imagen. La imagen no cabe en un zip: el límite de 250 MB es el
# del empaquetado zip, no el de contenedor, que llega a 10 GB.
# ---------------------------------------------------------------------------

resource "aws_ecr_repository" "api" {
  name                 = var.project
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Conservar solo las 10 imágenes más recientes"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 10
      }
      action = { type = "expire" }
    }]
  })
}

# ---------------------------------------------------------------------------
# Permisos. Un solo rol: leer y escribir en el bucket de media, llamar a
# Bedrock y escribir logs.
# ---------------------------------------------------------------------------

resource "aws_iam_role" "lambda" {
  name = "${var.project}-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "${var.project}-lambda"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
        Resource = "${aws_s3_bucket.media.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:ListBucket"]
        Resource = aws_s3_bucket.media.arn
      },
      {
        Effect   = "Allow"
        Action   = ["logs:CreateLogStream", "logs:PutLogEvents"]
        Resource = "${aws_cloudwatch_log_group.api.arn}:*"
      }
    ]
  })
}

# Se declara explícitamente para fijar la retención: si lo crea Lambda, los logs
# se guardan para siempre.
resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${var.project}"
  retention_in_days = 14
}

# ---------------------------------------------------------------------------
# La función. Sin VPC: dentro de una haría falta un NAT para salir a Bedrock.
# ---------------------------------------------------------------------------

resource "aws_lambda_function" "api" {
  function_name = var.project
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"

  memory_size = var.lambda_memory_mb
  timeout     = 60
  ephemeral_storage {
    size = 1024 # /tmp: imagenes en proceso
  }

  environment {
    variables = {
      ESTADO_BUCKET  = aws_s3_bucket.media.id
      STEGO_REGISTRO = var.registro_passphrase
    }
  }

  depends_on = [aws_cloudwatch_log_group.api]
}


# Solo esta distribución de CloudFront puede invocar la Function URL. Sin esto
# la URL quedaría accesible por internet saltándose el CDN.

# ---------------------------------------------------------------------------
# API Gateway HTTP API. Sustituye a la Function URL, que devolvia 403 tanto con
# AWS_IAM como con NONE pese a tener la politica y el OAC correctos.
# Ruta : todo lo que entra va a la Lambda y el enrutado lo hace FastAPI.
# ---------------------------------------------------------------------------

resource "aws_apigatewayv2_api" "api" {
  name          = var.project
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "api" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.api.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 30000
}

resource "aws_apigatewayv2_route" "api" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.api.id}"
}

# Stage : sin prefijo de etapa en la ruta, asi /api/emisores llega tal cual.
resource "aws_apigatewayv2_stage" "api" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowApiGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}
