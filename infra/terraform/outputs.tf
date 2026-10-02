output "load_balancer_url" {
  description = "HTTP endpoint for the portfolio service when desired_count is greater than zero."
  value       = "http://${aws_lb.app.dns_name}"
}

output "ecr_repository_url" {
  description = "ECR repository for application images."
  value       = aws_ecr_repository.app.repository_url
}

output "database_endpoint" {
  description = "Private PostgreSQL endpoint."
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "cloudwatch_log_group" {
  value = aws_cloudwatch_log_group.app.name
}
