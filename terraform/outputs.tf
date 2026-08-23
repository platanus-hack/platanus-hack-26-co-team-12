output "url" {
  description = "Dónde queda la aplicación."
  value       = local.usa_dominio ? "https://${var.domain_name}" : "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "ecr_repository_url" {
  description = "Destino del docker push."
  value       = aws_ecr_repository.api.repository_url
}

output "bucket_front" {
  description = "Destino del aws s3 sync del front."
  value       = aws_s3_bucket.front.id
}

output "bucket_media" {
  description = "Audios, llaves y gráficas."
  value       = aws_s3_bucket.media.id
}

output "distribution_id" {
  description = "Para invalidar la caché tras un despliegue."
  value       = aws_cloudfront_distribution.web.id
}

output "rol_despliegue" {
  description = "ARN que GitHub Actions debe asumir."
  value       = var.github_repo != "" ? aws_iam_role.deploy[0].arn : null
}

output "nameservers" {
  description = "Ponlos en tu registrador. Sin esto el certificado no valida."
  value       = local.usa_dominio && var.hosted_zone_id == "" ? aws_route53_zone.web[0].name_servers : null
}
