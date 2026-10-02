variable "aws_region" {
  description = "AWS region for the portfolio deployment."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix used for AWS resources."
  type        = string
  default     = "mdts-whatsapp-bot"
}

variable "container_port" {
  description = "Container port exposed by the Flask service."
  type        = number
  default     = 5000
}

variable "container_image" {
  description = "Container image URI to run in ECS."
  type        = string
  default     = "public.ecr.aws/docker/library/python:3.12-slim"
}

variable "database_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "mdts"
}

variable "database_username" {
  description = "PostgreSQL administrator username."
  type        = string
  default     = "mdts_admin"
}

variable "database_password" {
  description = "PostgreSQL administrator password. Supply through TF_VAR_database_password or a secure CI secret."
  type        = string
  sensitive   = true
}

variable "desired_count" {
  description = "Number of ECS tasks. Zero is allowed for a no-cost dormant portfolio configuration."
  type        = number
  default     = 0

  validation {
    condition     = var.desired_count >= 0
    error_message = "desired_count must be zero or greater."
  }
}
