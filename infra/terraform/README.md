# AWS / Terraform architecture

This directory demonstrates how the WhatsApp repair-operations backend can be deployed to AWS without requiring a continuously running portfolio environment.

## Architecture

- Amazon VPC with public and private subnets across two availability zones
- Application Load Balancer
- ECS Fargate service
- Amazon ECR repository with immutable tags and scan-on-push
- Amazon RDS for PostgreSQL in private subnets
- CloudWatch Logs
- least-privilege network boundaries between ALB, service, and database

The default `desired_count = 0` intentionally keeps the service dormant unless someone explicitly chooses to deploy workloads. Terraform code is present for engineering review without requiring ongoing hosting spend.

## Validation

No AWS credentials are required for formatting and static validation after provider initialization.

```bash
terraform init -backend=false
terraform fmt -check -recursive
terraform validate
```

## Secrets

Database passwords, Twilio credentials, and application secrets are not stored in Terraform source. For a real deployment, application secrets should be injected through a managed secret store such as AWS Secrets Manager or SSM Parameter Store and referenced by the ECS task definition.

## Production extensions

A production implementation would add:

- HTTPS/ACM and DNS
- NAT or VPC endpoints for private ECS tasks
- Secrets Manager references in the task definition
- autoscaling policies
- RDS deletion protection and longer backups
- WAF/rate limiting
- alarms and SLO-based observability
- remote Terraform state with locking
