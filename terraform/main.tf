terraform {
  required_version = ">= 1.6.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
  backend "s3" {
    # Configure via -backend-config flags or env vars:
    # bucket         = "lbro-tfstate"
    # key            = "lbro/terraform.tfstate"
    # region         = "us-east-1"
    # dynamodb_table = "lbro-tfstate-lock"
    # encrypt        = true
  }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "LBRO"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id  = data.aws_caller_identity.current.account_id
  region      = data.aws_region.current.name
  name_prefix = "lbro-${var.environment}"
}

# ── SNS alerts topic (created early — referenced by monitoring) ────────────────
resource "aws_sns_topic" "alerts" {
  name = "${local.name_prefix}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  count     = var.alert_email != "" ? 1 : 0
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

# ── Secrets Manager ────────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "app_secret_key" {
  name                    = "${local.name_prefix}/app-secret-key"
  recovery_window_in_days = 7
  description             = "LBRO application secret key for JWT signing"
}

resource "aws_secretsmanager_secret_version" "app_secret_key" {
  secret_id     = aws_secretsmanager_secret.app_secret_key.id
  secret_string = var.app_secret_key
}

resource "aws_secretsmanager_secret" "db_password" {
  name                    = "${local.name_prefix}/db-password"
  recovery_window_in_days = 7
  description             = "LBRO RDS PostgreSQL password (raw — used by RDS module)"
}

resource "random_password" "db_password" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret_version" "db_password" {
  secret_id     = aws_secretsmanager_secret.db_password.id
  secret_string = random_password.db_password.result
}

# Full DATABASE_URL secret — built after RDS is created (references module.rds outputs).
# ECS tasks use this secret so they get a complete asyncpg connection string, not just the password.
resource "aws_secretsmanager_secret" "db_url" {
  name                    = "${local.name_prefix}/db-url"
  recovery_window_in_days = 7
  description             = "LBRO full DATABASE_URL for asyncpg (postgresql+asyncpg://...)"
}

resource "aws_secretsmanager_secret_version" "db_url" {
  secret_id = aws_secretsmanager_secret.db_url.id
  secret_string = format(
    "postgresql+asyncpg://lbro:%s@%s:%s/%s",
    random_password.db_password.result,
    module.rds.db_endpoint,
    module.rds.db_port,
    module.rds.db_name,
  )
}

# ── Networking ─────────────────────────────────────────────────────────────────
module "networking" {
  source = "./modules/networking"

  name_prefix = local.name_prefix
  vpc_cidr    = var.vpc_cidr
  az_count    = var.az_count
  environment = var.environment
}

# ── SQS ───────────────────────────────────────────────────────────────────────
module "sqs" {
  source = "./modules/sqs"

  name_prefix = local.name_prefix
  environment = var.environment
}

# ── S3 ────────────────────────────────────────────────────────────────────────
module "s3" {
  source = "./modules/s3"

  name_prefix   = local.name_prefix
  environment   = var.environment
  force_destroy = var.environment != "production"
}

# ── IAM ───────────────────────────────────────────────────────────────────────
module "iam" {
  source = "./modules/iam"

  name_prefix            = local.name_prefix
  environment            = var.environment
  evidence_bucket_arn    = module.s3.evidence_bucket_arn
  reports_bucket_arn     = module.s3.reports_bucket_arn
  ml_models_bucket_arn   = module.s3.ml_models_bucket_arn
  incident_queue_arn     = module.sqs.incident_queue_arn
  notification_queue_arn = module.sqs.notification_queue_arn
  dlq_arn                = module.sqs.dlq_arn
  secrets_arns = [
    aws_secretsmanager_secret.app_secret_key.arn,
    aws_secretsmanager_secret.db_password.arn,
    aws_secretsmanager_secret.db_url.arn,
  ]
}

# ── ECS Fargate ───────────────────────────────────────────────────────────────
module "ecs" {
  source = "./modules/ecs"

  name_prefix          = local.name_prefix
  environment          = var.environment
  aws_region           = var.aws_region
  vpc_id               = module.networking.vpc_id
  public_subnet_ids    = module.networking.public_subnet_ids
  private_subnet_ids   = module.networking.private_subnet_ids
  execution_role_arn   = module.iam.execution_role_arn
  task_role_arn        = module.iam.task_role_arn

  api_image              = var.api_image
  worker_image           = var.worker_image
  frontend_image         = var.frontend_image
  api_cpu                = var.api_cpu
  api_memory             = var.api_memory
  worker_cpu             = var.worker_cpu
  worker_memory          = var.worker_memory
  api_desired_count      = var.api_desired_count
  worker_desired_count   = var.worker_desired_count

  api_env_vars = [
    { name = "ENVIRONMENT",                value = var.environment },
    { name = "AWS_DEFAULT_REGION",         value = var.aws_region },
    # env var names must match config.py settings (S3_BUCKET_EVIDENCE, S3_BUCKET_REPORTS)
    { name = "S3_BUCKET_EVIDENCE",         value = module.s3.evidence_bucket_name },
    { name = "S3_BUCKET_REPORTS",          value = module.s3.reports_bucket_name },
    { name = "SQS_INCIDENT_QUEUE_URL",     value = module.sqs.incident_queue_url },
    { name = "SQS_NOTIFICATION_QUEUE_URL", value = module.sqs.notification_queue_url },
    # CORS_ORIGINS can't reference module.ecs.alb_dns_name (self-reference).
    # Set via var.cors_origins; after first deploy, run: terraform apply -var cors_origins=https://your-alb-dns
    { name = "CORS_ORIGINS",               value = var.cors_origins },
  ]
  api_secrets = [
    { name = "SECRET_KEY",   valueFrom = aws_secretsmanager_secret.app_secret_key.arn },
    # DATABASE_URL secret contains the full asyncpg connection string (not just the password)
    { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.db_url.arn },
  ]

  worker_env_vars = [
    { name = "ENVIRONMENT",                value = var.environment },
    { name = "AWS_DEFAULT_REGION",         value = var.aws_region },
    { name = "S3_BUCKET_EVIDENCE",         value = module.s3.evidence_bucket_name },
    { name = "SQS_INCIDENT_QUEUE_URL",     value = module.sqs.incident_queue_url },
    { name = "SQS_NOTIFICATION_QUEUE_URL", value = module.sqs.notification_queue_url },
  ]
  worker_secrets = [
    { name = "SECRET_KEY",   valueFrom = aws_secretsmanager_secret.app_secret_key.arn },
    { name = "DATABASE_URL", valueFrom = aws_secretsmanager_secret.db_url.arn },
  ]

  # No depends_on [module.rds] — that created a circular dependency:
  #   module.ecs depends_on module.rds  AND  module.rds uses module.ecs.api_sg_id
  # The runtime ordering (ECS tasks retry until DB is ready) handles startup sequencing.
}

# ── RDS (after ECS so we can pass api_sg_id as allowed_sg_ids) ────────────────
module "rds" {
  source = "./modules/rds"

  name_prefix         = local.name_prefix
  environment         = var.environment
  vpc_id              = module.networking.vpc_id
  subnet_ids          = module.networking.private_subnet_ids
  instance_class      = var.db_instance_class
  db_password         = random_password.db_password.result
  allowed_sg_ids      = [module.ecs.api_sg_id, module.ecs.worker_sg_id]
  deletion_protection = var.environment == "production"
}

# ── CloudWatch Monitoring ──────────────────────────────────────────────────────
module "monitoring" {
  source = "./modules/monitoring"

  name_prefix                  = local.name_prefix
  environment                  = var.environment
  sns_topic_arn                = aws_sns_topic.alerts.arn
  ecs_cluster_name             = module.ecs.cluster_name
  api_service_name             = module.ecs.api_service_name
  worker_service_name          = module.ecs.worker_service_name
  dlq_name                     = module.sqs.dlq_name
  dlq_arn                      = module.sqs.dlq_arn
  rds_instance_id              = module.rds.db_identifier
  alb_arn_suffix               = module.ecs.alb_arn_suffix
  api_target_group_arn_suffix  = module.ecs.api_target_group_arn_suffix
}

