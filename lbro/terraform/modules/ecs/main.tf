################################################################################
# LBRO — ECS Fargate Module (Scalability-optimised)
#
# Scalability additions vs previous version:
#   1. FARGATE_SPOT mixed strategy — workers burst cheaply on spot, API on on-demand
#   2. Separate scale-out / scale-in cooldowns — fast up, slow down
#   3. ALB connection draining tuned for fast rolling deploys
#   4. ECS capacity provider weighted strategy at service level
#   5. X-Ray daemon sidecar in task definitions for distributed tracing
#   6. Container-level resource reservations prevent noisy-neighbour starvation
################################################################################

resource "aws_ecr_repository" "api" {
  name                 = "${var.name}/api"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "KMS"; kms_key = var.kms_key_arn }
  tags = merge(var.tags, { Name = "${var.name}-ecr-api" })
}

resource "aws_ecr_repository" "worker" {
  name                 = "${var.name}/worker"
  image_tag_mutability = "IMMUTABLE"
  image_scanning_configuration { scan_on_push = true }
  encryption_configuration { encryption_type = "KMS"; kms_key = var.kms_key_arn }
  tags = merge(var.tags, { Name = "${var.name}-ecr-worker" })
}

resource "aws_ecr_lifecycle_policy" "api" {
  repository = aws_ecr_repository.api.name
  policy = jsonencode({ rules = [{ rulePriority = 1; description = "Keep last 10 images"
    selection = { tagStatus = "any"; countType = "imageCountMoreThan"; countNumber = 10 }
    action = { type = "expire" } }] })
}

resource "aws_ecr_lifecycle_policy" "worker" {
  repository = aws_ecr_repository.worker.name
  policy = jsonencode({ rules = [{ rulePriority = 1; description = "Keep last 10 images"
    selection = { tagStatus = "any"; countType = "imageCountMoreThan"; countNumber = 10 }
    action = { type = "expire" } }] })
}

resource "aws_ecs_cluster" "this" {
  name = "${var.name}-cluster"
  setting { name = "containerInsights"; value = var.enable_container_insights ? "enabled" : "disabled" }
  tags = merge(var.tags, { Name = "${var.name}-cluster" })
}

resource "aws_ecs_cluster_capacity_providers" "this" {
  cluster_name       = aws_ecs_cluster.this.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  # Default strategy: API uses ON_DEMAND (SLA reliability), workers mix in SPOT
  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/ecs/${var.name}/api"
  retention_in_days = 30
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/ecs/${var.name}/worker"
  retention_in_days = 30
  kms_key_id        = var.kms_key_arn
  tags              = var.tags
}

resource "aws_security_group" "alb" {
  name        = "${var.name}-alb-sg"
  description = "ALB — HTTPS/HTTP inbound, HTTPS only after redirect"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 443; to_port = 443; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]; ipv6_cidr_blocks = ["::/0"]
    description = "HTTPS from internet"
  }
  ingress {
    from_port = 80; to_port = 80; protocol = "tcp"
    cidr_blocks = ["0.0.0.0/0"]; ipv6_cidr_blocks = ["::/0"]
    description = "HTTP redirect only"
  }
  egress {
    from_port = 8000; to_port = 8000; protocol = "tcp"
    cidr_blocks = [var.vpc_cidr]; description = "To ECS tasks"
  }
  tags = merge(var.tags, { Name = "${var.name}-alb-sg" })
}

resource "aws_security_group" "ecs_api" {
  name        = "${var.name}-ecs-api-sg"
  description = "API tasks — allow from ALB only"
  vpc_id      = var.vpc_id

  ingress {
    from_port = 8000; to_port = 8000; protocol = "tcp"
    security_groups = [aws_security_group.alb.id]; description = "From ALB"
  }
  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]; description = "Outbound to AWS services via VPC endpoints"
  }
  tags = merge(var.tags, { Name = "${var.name}-ecs-api-sg" })
}

resource "aws_security_group" "ecs_worker" {
  name        = "${var.name}-ecs-worker-sg"
  description = "Worker tasks — no inbound, outbound only"
  vpc_id      = var.vpc_id

  egress {
    from_port = 0; to_port = 0; protocol = "-1"
    cidr_blocks = ["0.0.0.0/0"]; description = "SQS, S3 via VPC endpoints"
  }
  tags = merge(var.tags, { Name = "${var.name}-ecs-worker-sg" })
}

resource "aws_lb" "this" {
  name               = "${var.name}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = var.public_subnet_ids

  enable_deletion_protection       = var.environment == "prod"
  enable_cross_zone_load_balancing = true
  drop_invalid_header_fields       = true
  idle_timeout                     = 60

  access_logs {
    bucket  = var.alb_access_log_bucket
    prefix  = "alb/${var.name}"
    enabled = true
  }
  tags = merge(var.tags, { Name = "${var.name}-alb" })
}

resource "aws_lb_target_group" "api" {
  name        = "${var.name}-api-tg"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 15       # Check every 15s for faster scale detection
    path                = "/health"
    matcher             = "200"
  }

  # Tuned for fast rolling deploys — reduce drain time so old tasks die quickly
  deregistration_delay = 20

  stickiness {
    type    = "lb_cookie"
    enabled = false   # Stateless API — no stickiness needed
  }

  tags = merge(var.tags, { Name = "${var.name}-api-tg" })
  lifecycle { create_before_destroy = true }
}

resource "aws_lb_listener" "http_redirect" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect { port = "443"; protocol = "HTTPS"; status_code = "HTTP_301" }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.this.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.acm_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.arn
  }
}

################################################################################
# ECS Task Definitions
# X-Ray daemon sidecar enables distributed tracing without SDK changes
################################################################################

resource "aws_ecs_task_definition" "api" {
  family                   = "${var.name}-api"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.api_cpu
  memory                   = var.api_memory
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_api_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "api"
      image     = "${aws_ecr_repository.api.repository_url}:${var.image_tag}"
      essential = true

      portMappings = [{ containerPort = 8000; protocol = "tcp" }]

      # Reserve memory hard limit below task total to leave headroom for X-Ray sidecar
      memoryReservation = floor(var.api_memory * 0.85)

      environment = [
        { name = "APP_ENV",       value = var.environment },
        { name = "AWS_REGION",    value = var.aws_region },
        { name = "LOG_LEVEL",     value = var.environment == "prod" ? "INFO" : "DEBUG" },
        # X-Ray daemon runs as a sidecar on localhost:2000
        { name = "AWS_XRAY_DAEMON_ADDRESS", value = "localhost:2000" },
      ]

      secrets = [
        { name = "DATABASE_URL",  valueFrom = "${var.secrets_arn}:database_url::" },
        { name = "SECRET_KEY",    valueFrom = "${var.secrets_arn}:secret_key::" },
        { name = "API_KEY",       valueFrom = "${var.secrets_arn}:api_key::" },
        { name = "SQS_QUEUE_URL", valueFrom = "${var.secrets_arn}:sqs_queue_url::" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "api"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -sf http://localhost:8000/health || exit 1"]
        interval    = 15
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      readonlyRootFilesystem = true
      user                   = "1000:1000"
      ulimits = [{ name = "nofile"; softLimit = 65536; hardLimit = 65536 }]
    },
    # X-Ray daemon sidecar — captures traces from app and forwards to AWS X-Ray
    {
      name      = "xray-daemon"
      image     = "public.ecr.aws/xray/aws-xray-daemon:latest"
      essential = false   # Don't kill the task if X-Ray daemon dies

      portMappings = [{ containerPort = 2000; protocol = "udp" }]
      memoryReservation = 64

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.api.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "xray"
        }
      }
    }
  ])

  tags = var.tags
}

resource "aws_ecs_task_definition" "worker" {
  family                   = "${var.name}-worker"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.worker_cpu
  memory                   = var.worker_memory
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_worker_task_role_arn

  container_definitions = jsonencode([
    {
      name      = "worker"
      image     = "${aws_ecr_repository.worker.repository_url}:${var.image_tag}"
      essential = true
      memoryReservation = floor(var.worker_memory * 0.85)

      environment = [
        { name = "APP_ENV",     value = var.environment },
        { name = "AWS_REGION",  value = var.aws_region },
        { name = "LOG_LEVEL",   value = var.environment == "prod" ? "INFO" : "DEBUG" },
        { name = "WORKER_MODE", value = "true" },
        { name = "AWS_XRAY_DAEMON_ADDRESS", value = "localhost:2000" },
      ]

      secrets = [
        { name = "DATABASE_URL",        valueFrom = "${var.secrets_arn}:database_url::" },
        { name = "SECRET_KEY",          valueFrom = "${var.secrets_arn}:secret_key::" },
        { name = "SQS_QUEUE_URL",       valueFrom = "${var.secrets_arn}:sqs_queue_url::" },
        { name = "S3_EVIDENCE_BUCKET",  valueFrom = "${var.secrets_arn}:s3_evidence_bucket::" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "worker"
        }
      }

      readonlyRootFilesystem = true
      user                   = "1000:1000"
      # Give the worker 30 seconds to finish its in-flight SQS message on SIGTERM
      stopTimeout            = 30
    },
    {
      name      = "xray-daemon"
      image     = "public.ecr.aws/xray/aws-xray-daemon:latest"
      essential = false
      portMappings = [{ containerPort = 2000; protocol = "udp" }]
      memoryReservation = 64
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.worker.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "xray-worker"
        }
      }
    }
  ])

  tags = var.tags
}

################################################################################
# ECS Services — capacity provider strategy separates API (on-demand) from
# workers (mixed spot/on-demand for cost efficiency at burst scale)
################################################################################

resource "aws_ecs_service" "api" {
  name                              = "${var.name}-api"
  cluster                           = aws_ecs_cluster.this.id
  task_definition                   = aws_ecs_task_definition.api.arn
  desired_count                     = var.api_desired_count
  health_check_grace_period_seconds = 60

  # API: always on-demand — SLA critical, can't afford spot interruption
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = var.api_desired_count
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_api.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.api.arn
    container_name   = "api"
    container_port   = 8000
  }

  deployment_circuit_breaker { enable = true; rollback = true }
  deployment_controller { type = "ECS" }

  # Minimum healthy percent during deploy: 100% means rolling, no downtime
  deployment_minimum_healthy_percent = 100
  deployment_maximum_percent         = 200

  enable_execute_command = var.environment != "prod"

  tags = merge(var.tags, { Name = "${var.name}-api-service" })
  lifecycle { ignore_changes = [desired_count] }
  depends_on = [aws_lb_listener.https]
}

resource "aws_ecs_service" "worker" {
  name            = "${var.name}-worker"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.worker.arn
  desired_count   = var.worker_desired_count

  # Workers: 1 guaranteed on-demand base, burst on FARGATE_SPOT (60-70% cheaper)
  capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1   # Always keep 1 on-demand worker running
  }
  capacity_provider_strategy {
    capacity_provider = "FARGATE_SPOT"
    weight            = 3   # 75% of scale-out goes to spot
    base              = 0
  }

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [aws_security_group.ecs_worker.id]
    assign_public_ip = false
  }

  deployment_circuit_breaker { enable = true; rollback = true }

  tags = merge(var.tags, { Name = "${var.name}-worker-service" })
  lifecycle { ignore_changes = [desired_count] }
}

################################################################################
# Auto-scaling — separate policies for scale-out speed vs scale-in caution
################################################################################

resource "aws_appautoscaling_target" "api" {
  max_capacity       = var.api_max_count
  min_capacity       = var.api_desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.api.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

resource "aws_appautoscaling_policy" "api_cpu" {
  name               = "${var.name}-api-cpu-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 65.0   # Scale out at 65% CPU — headroom before saturation
    scale_out_cooldown = 60     # Fast scale-out: 1 minute
    scale_in_cooldown  = 300    # Slow scale-in: 5 minutes (avoid flapping)
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageCPUUtilization" }
  }
}

resource "aws_appautoscaling_policy" "api_memory" {
  name               = "${var.name}-api-memory-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.api.resource_id
  scalable_dimension = aws_appautoscaling_target.api.scalable_dimension
  service_namespace  = aws_appautoscaling_target.api.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 70.0
    scale_out_cooldown = 60
    scale_in_cooldown  = 300
    predefined_metric_specification { predefined_metric_type = "ECSServiceAverageMemoryUtilization" }
  }
}

resource "aws_appautoscaling_target" "worker" {
  max_capacity       = var.worker_max_count
  min_capacity       = var.worker_desired_count
  resource_id        = "service/${aws_ecs_cluster.this.name}/${aws_ecs_service.worker.name}"
  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}

# Workers scale on SQS queue depth — 1 worker per 5 queued messages
resource "aws_appautoscaling_policy" "worker_sqs" {
  name               = "${var.name}-worker-sqs-scaling"
  policy_type        = "TargetTrackingScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value       = 5.0   # 1 worker per 5 visible messages
    scale_out_cooldown = 30    # Very fast scale-out for breach response
    scale_in_cooldown  = 120   # Moderate scale-in

    customized_metric_specification {
      metric_name = "ApproximateNumberOfMessagesVisible"
      namespace   = "AWS/SQS"
      statistic   = "Average"
      dimensions { name = "QueueName"; value = var.incident_queue_name }
    }
  }
}

# Step scaling for sudden spikes — immediately add 3 workers when queue > 20 messages
resource "aws_appautoscaling_policy" "worker_spike" {
  name               = "${var.name}-worker-spike-scaling"
  policy_type        = "StepScaling"
  resource_id        = aws_appautoscaling_target.worker.resource_id
  scalable_dimension = aws_appautoscaling_target.worker.scalable_dimension
  service_namespace  = aws_appautoscaling_target.worker.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ChangeInCapacity"
    cooldown                = 30
    metric_aggregation_type = "Maximum"

    step_adjustment {
      scaling_adjustment          = 3
      metric_interval_lower_bound = 0   # When alarm fires (queue > 20), add 3 workers
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "worker_spike_alarm" {
  alarm_name          = "${var.name}-worker-queue-spike"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 1
  metric_name         = "ApproximateNumberOfMessagesVisible"
  namespace           = "AWS/SQS"
  period              = 60
  statistic           = "Maximum"
  threshold           = 20   # Spike alarm: queue depth > 20

  dimensions        = { QueueName = var.incident_queue_name }
  alarm_actions     = [aws_appautoscaling_policy.worker_spike.arn]
  treat_missing_data = "notBreaching"
  tags               = var.tags
}
