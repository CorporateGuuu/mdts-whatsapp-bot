provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = var.project_name
      ManagedBy = "terraform"
      Purpose   = "portfolio"
    }
  }
}

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 2)
}

resource "aws_vpc" "main" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = { Name = "${var.project_name}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = { Name = "${var.project_name}-igw" }
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  availability_zone       = local.azs[count.index]
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index)
  map_public_ip_on_launch = true

  tags = { Name = "${var.project_name}-public-${count.index + 1}" }
}

resource "aws_subnet" "private" {
  count             = 2
  vpc_id            = aws_vpc.main.id
  availability_zone = local.azs[count.index]
  cidr_block        = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 10)

  tags = { Name = "${var.project_name}-private-${count.index + 1}" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "alb" {
  name        = "${var.project_name}-alb"
  description = "Public HTTP ingress to the application load balancer."
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "service" {
  name        = "${var.project_name}-service"
  description = "Only ALB traffic may reach the ECS task."
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "database" {
  name        = "${var.project_name}-database"
  description = "PostgreSQL ingress only from the ECS service."
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.service.id]
  }
}

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnets"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "postgres" {
  identifier              = "${var.project_name}-postgres"
  engine                  = "postgres"
  engine_version          = "16"
  instance_class          = "db.t4g.micro"
  allocated_storage       = 20
  storage_encrypted       = true
  db_name                 = var.database_name
  username                = var.database_username
  password                = var.database_password
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.database.id]
  publicly_accessible     = false
  skip_final_snapshot     = true
  deletion_protection     = false
  backup_retention_period = 1
}

resource "aws_ecr_repository" "app" {
  name                 = var.project_name
  image_tag_mutability = "IMMUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 14
}

resource "aws_iam_role" "ecs_execution" {
  name = "${var.project_name}-ecs-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecs_cluster" "main" {
  name = var.project_name
}

resource "aws_lb" "app" {
  name               = substr(var.project_name, 0, 32)
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
}

resource "aws_lb_target_group" "app" {
  name        = substr("${var.project_name}-tg", 0, 32)
  port        = var.container_port
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = aws_vpc.main.id

  health_check {
    path                = "/healthz"
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.app.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.project_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = 256
  memory                   = 512
  execution_role_arn       = aws_iam_role.ecs_execution.arn

  container_definitions = jsonencode([{
    name         = "app"
    image        = var.container_image
    essential    = true
    portMappings = [{
      containerPort = var.container_port
      hostPort      = var.container_port
      protocol      = "tcp"
    }]
    environment = [
      { name = "PORT", value = tostring(var.container_port) },
      { name = "AWS_REGION", value = var.aws_region }
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "app"
      }
    }
  }])
}

resource "aws_ecs_service" "app" {
  name            = var.project_name
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.service.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = "app"
    container_port   = var.container_port
  }

  depends_on = [aws_lb_listener.http]
}
