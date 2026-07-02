################################################################################
# LBRO — Dev Environment
#
# Module dependency order (Terraform resolves via references):
#   secrets → sns_alerts → sqs → iam → s3 → ecs → rds → monitoring
#
# Scalability config (dev-sized, prod switches in environments/prod/main.tf):
#   - RDS Proxy: enabled (cheap at this scale, validates prod config)
#   - Read replica: disabled in dev (cost saving — enable for load testing)
#   - Worker spot: enabled (FARGATE_SPOT for burst workers)
#   - Step scaling: enabled for SQS spike handling
################################################################################

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  backend "s3" {
    bucket         = "lbro-tf-state-dev"
    key            = "dev/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "lbro-tf-lock-dev"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = local.common_tags
  }
}

locals {
  name        = "lbro-dev"
  environment = "dev"

  common_tags = {
    Project     = "LBRO"
    Environment = local.environment
    ManagedBy   = "Terraform"
    Owner       = var.owner_team
  }
}

################################################################################
# Secrets — first; ARN needed by ECS task definitions
################################################################################

module "secrets" {
  source      = "../../modules/secrets"
  name        = local.name
  environment = local.environment
  tags        = local.common_tags
}

################################################################################
# SNS Alerts — declared early so SQS and RDS can reference without circular dep
################################################################################

resource "aws_sns_topic" "alerts" {
  name              = "${local.name}-alerts"
  kms_master_key_id = module.secrets.kms_key_id
  tags              = local.common_tags
}

resource "aws_sns_topic_subscription" "email" {
  for_each  = toset(var.alert_emails)
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

################################################################################
# VPC
################################################################################

module "vpc" {
  source             = "../../modules/vpc"
  name               = local.name
  vpc_cidr           = "10.0.0.0/16"
  aws_region         = var.aws_region
  enable_nat_gateway      = true
  single_nat_gateway      = true   # Dev only: 1 NAT GW saves $64/mo vs 3
  tags               = local.common_tags
}

################################################################################
# SQS — real IAM ARNs wired in (Terraform resolves cross-module references)
################################################################################

module "sqs" {
  source     = "../../modules/sqs"
  name       = local.name
  vpc_id     = module.vpc.vpc_id
  kms_key_id = module.secrets.kms_key_id

  allowed_principal_arns = [
    module.iam.ecs_api_task_role_arn,
    module.iam.ecs_worker_task_role_arn,
  ]

  alarm_sns_topic_arns = [aws_sns_topic.alerts.arn]
  tags                 = local.common_tags
}

################################################################################
# IAM
################################################################################

module "iam" {
  source      = "../../modules/iam"
  name        = local.name
  secrets_arn = module.secrets.secret_arn
  kms_key_arn = module.secrets.kms_key_arn

  s3_kms_key_arn           = module.s3.s3_kms_key_arn
  sqs_queue_arns           = module.sqs.all_queue_arns
  evidence_bucket_arn      = module.s3.evidence_bucket_arn
  notifications_bucket_arn = module.s3.notifications_bucket_arn

  tags = local.common_tags
}

################################################################################
# S3
################################################################################

module "s3" {
  source                   = "../../modules/s3"
  name                     = local.name
  worker_task_role_arn     = module.iam.ecs_worker_task_role_arn
  evidence_event_queue_arn = module.sqs.containment_actions_queue_arn
  tags                     = local.common_tags
}

################################################################################
# ECS — Fargate cluster, API + Worker services, ALB
################################################################################

module "ecs" {
  source      = "../../modules/ecs"
  name        = local.name
  environment = local.environment
  aws_region  = var.aws_region
  vpc_id      = module.vpc.vpc_id
  vpc_cidr    = module.vpc.vpc_cidr

  public_subnet_ids  = module.vpc.public_subnet_ids
  private_subnet_ids = module.vpc.private_subnet_ids

  kms_key_arn           = module.secrets.kms_key_arn
  secrets_arn           = module.secrets.secret_arn
  acm_certificate_arn   = var.acm_certificate_arn
  alb_access_log_bucket = module.s3.alb_logs_bucket_name
  incident_queue_name   = module.sqs.incident_events_queue_name

  ecs_execution_role_arn   = module.iam.ecs_execution_role_arn
  ecs_api_task_role_arn    = module.iam.ecs_api_task_role_arn
  ecs_worker_task_role_arn = module.iam.ecs_worker_task_role_arn

  api_cpu              = 256
  api_memory           = 512
  api_desired_count    = 1
  api_max_count        = 4
  worker_cpu           = 512
  worker_memory        = 1024
  worker_desired_count = 1
  worker_max_count     = 6

  # Cost saving: disable Container Insights in dev (~$8/mo)
  enable_container_insights = false

  image_tag = var.image_tag
  tags      = local.common_tags
}

################################################################################
# RDS — primary + proxy (replica disabled in dev, enabled in prod)
################################################################################

resource "random_password" "db" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

module "rds" {
  source               = "../../modules/rds"
  name                 = local.name
  environment          = local.environment
  aws_region           = var.aws_region
  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.db_subnet_group_name
  db_subnet_ids        = module.vpc.db_subnet_ids
  kms_key_arn          = module.secrets.kms_key_arn
  # RDS Proxy: disabled in dev to save $22/mo. Enable in prod.
  enable_rds_proxy     = false
  db_secret_arn        = module.secrets.secret_arn

  allowed_sg_ids = [
    module.ecs.api_sg_id,
    module.ecs.worker_sg_id,
    # rds_proxy_sg_id is added via a separate aws_security_group_rule after creation
    # to avoid a circular dependency (rds module creates the proxy SG itself)
  ]

  db_password             = random_password.db.result
  instance_class          = "db.t4g.micro"
  allocated_storage       = 20
  max_allocated_storage   = 50
  max_connections         = "100"
  create_read_replica     = false   # Enable for load testing or prod

  alarm_sns_topic_arns = [aws_sns_topic.alerts.arn]
  tags                 = local.common_tags
}

################################################################################
# Monitoring
################################################################################

module "monitoring" {
  source       = "../../modules/monitoring"
  name         = local.name
  kms_key_id   = module.secrets.kms_key_id
  alert_emails = var.alert_emails

  alb_arn_suffix          = module.ecs.alb_arn_suffix
  ecs_cluster_name        = module.ecs.cluster_name
  api_service_name        = module.ecs.api_service_name
  worker_service_name     = module.ecs.worker_service_name
  db_instance_id          = module.rds.db_instance_id
  incident_queue_name     = module.sqs.incident_events_queue_name
  containment_queue_name  = module.sqs.containment_actions_queue_name
  notification_queue_name = module.sqs.notification_dispatch_queue_name
  alerts_sns_topic_arn    = aws_sns_topic.alerts.arn

  tags = local.common_tags
}

################################################################################
# Secrets — wire real values after all infrastructure is created
# ECS tasks read individual JSON keys via secrets valueFrom: "arn:secret_id:key::"
################################################################################

resource "aws_secretsmanager_secret_version" "app_real" {
  secret_id = module.secrets.secret_arn

  secret_string = jsonencode({
    # App connects via RDS Proxy for connection pooling at scale
    # Plain postgresql:// — app's ensure_asyncpg_and_ssl validator adds driver + SSL
    # Dev: direct RDS endpoint (no proxy). Prod: use module.rds.proxy_endpoint
    database_url       = "postgresql://lbro_app:${random_password.db.result}@${module.rds.db_host}:${module.rds.db_port}/lbro"
    secret_key         = "REPLACE_WITH_STRONG_KEY_BEFORE_FIRST_DEPLOY"
    api_key            = "REPLACE_WITH_STRONG_API_KEY_BEFORE_FIRST_DEPLOY"
    sqs_queue_url      = module.sqs.incident_events_queue_url
    s3_evidence_bucket = module.s3.evidence_bucket_id
  })

  lifecycle {
    ignore_changes = [secret_string]
  }

  depends_on = [module.rds, module.sqs, module.s3]
}

################################################################################
# Post-creation: allow RDS to accept connections from RDS Proxy
# Done here (not in the rds module) to avoid the circular dependency where
# rds module would need its own output as an input.
################################################################################

resource "aws_security_group_rule" "rds_from_proxy" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.rds.rds_proxy_sg_id
  security_group_id        = module.rds.rds_sg_id
  description              = "Allow RDS Proxy to connect to RDS"
}

################################################################################
# WAF — protects ALB with managed rules + rate limiting + attack alarms
################################################################################

module "waf" {
  source      = "../../modules/waf"
  name        = local.name
  aws_region  = var.aws_region
  alb_arn     = module.ecs.alb_arn
  kms_key_arn = module.secrets.kms_key_arn

  # No geo-blocking in dev — add country codes in prod if needed
  blocked_country_codes          = []
  blocked_requests_alarm_threshold = 200
  alarm_sns_topic_arns           = [aws_sns_topic.alerts.arn]

  tags = local.common_tags
}

################################################################################
# EventBridge — deadline sweeper + evidence integrity scheduler
################################################################################

module "eventbridge" {
  source                 = "../../modules/eventbridge"
  name                   = local.name
  notification_queue_arn = module.sqs.notification_dispatch_queue_arn
  alerts_sns_topic_arn   = aws_sns_topic.alerts.arn
  tags                   = local.common_tags
}

################################################################################
# AWS Backup — centralised backup policy for RDS
################################################################################

module "backup" {
  source            = "../../modules/backup"
  name              = local.name
  rds_instance_arns = ["arn:aws:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:db:${module.rds.db_instance_id}"]

  alarm_sns_topic_arns = [aws_sns_topic.alerts.arn]
  backup_copy_region   = ""          # Set to "ap-southeast-1" in prod for DR
  enable_vault_lock    = false       # Enable in prod once config is verified
  tags                 = local.common_tags
}
