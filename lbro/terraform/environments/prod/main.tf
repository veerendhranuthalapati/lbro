################################################################################
# LBRO — Production Environment
#
# Differences from dev:
#   - Multi-AZ NAT Gateways (HA — no single_nat_gateway)
#   - RDS Multi-AZ + read replica
#   - RDS Proxy enabled
#   - Deletion protection on RDS + ALB
#   - Container Insights enabled
#   - AWS Backup vault lock enabled
#   - Cross-region backup copy to DR region
#   - Larger ECS task sizes and higher desired counts
#   - WAF with optional geo-blocking
#   - ECS Exec disabled (security hardening)
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
    bucket         = "lbro-tf-state-prod"
    key            = "prod/terraform.tfstate"
    region         = "ap-south-1"
    encrypt        = true
    dynamodb_table = "lbro-tf-lock-prod"
  }
}

provider "aws" {
  region = var.aws_region
  default_tags { tags = local.common_tags }
}

locals {
  name        = "lbro-prod"
  environment = "prod"
  common_tags = {
    Project     = "LBRO"
    Environment = local.environment
    ManagedBy   = "Terraform"
    Owner       = var.owner_team
  }
}

module "secrets" {
  source      = "../../modules/secrets"
  name        = local.name
  environment = local.environment
  tags        = local.common_tags
}

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

module "vpc" {
  source             = "../../modules/vpc"
  name               = local.name
  vpc_cidr           = "10.1.0.0/16"
  aws_region         = var.aws_region
  enable_nat_gateway = true
  single_nat_gateway = false  # Prod: HA — one NAT GW per AZ
  tags               = local.common_tags
}

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

module "iam" {
  source      = "../../modules/iam"
  name        = local.name
  secrets_arn = module.secrets.secret_arn
  kms_key_arn = module.secrets.kms_key_arn

  s3_kms_key_arn           = module.s3.s3_kms_key_arn
  sqs_queue_arns           = module.sqs.all_queue_arns
  evidence_bucket_arn      = module.s3.evidence_bucket_arn
  notifications_bucket_arn = module.s3.notifications_bucket_arn
  tags                     = local.common_tags
}

module "s3" {
  source                   = "../../modules/s3"
  name                     = local.name
  worker_task_role_arn     = module.iam.ecs_worker_task_role_arn
  evidence_event_queue_arn = module.sqs.containment_actions_queue_arn
  tags                     = local.common_tags
}

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

  # Prod sizing
  api_cpu              = 1024
  api_memory           = 2048
  api_desired_count    = 2     # Minimum 2 for HA across AZs
  api_max_count        = 20
  worker_cpu           = 1024
  worker_memory        = 2048
  worker_desired_count = 2
  worker_max_count     = 50    # Breach events can be bursty

  # Prod: Container Insights enabled for full observability
  enable_container_insights = true

  image_tag = var.image_tag
  tags      = local.common_tags
}

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
  db_secret_arn        = module.secrets.secret_arn

  allowed_sg_ids = [
    module.ecs.api_sg_id,
    module.ecs.worker_sg_id,
  ]

  db_password             = random_password.db.result
  instance_class          = "db.r8g.large"   # Prod: memory-optimised for query cache
  replica_instance_class  = "db.r8g.large"
  allocated_storage       = 100
  max_allocated_storage   = 1000
  max_connections         = "500"
  create_read_replica     = true    # Prod: read replica for GET /incidents queries
  enable_rds_proxy        = true    # Prod: connection pooling

  alarm_sns_topic_arns            = [aws_sns_topic.alerts.arn]
  max_connections_alarm_threshold = 400
  tags                            = local.common_tags
}

resource "aws_security_group_rule" "rds_from_proxy" {
  type                     = "ingress"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = module.rds.rds_proxy_sg_id
  security_group_id        = module.rds.rds_sg_id
  description              = "Allow RDS Proxy to connect to RDS"
}

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
  tags                    = local.common_tags
}

module "waf" {
  source      = "../../modules/waf"
  name        = local.name
  aws_region  = var.aws_region
  alb_arn     = module.ecs.alb_arn
  kms_key_arn = module.secrets.kms_key_arn

  blocked_country_codes             = var.blocked_country_codes
  blocked_requests_alarm_threshold  = 500
  alarm_sns_topic_arns              = [aws_sns_topic.alerts.arn]
  tags                              = local.common_tags
}

module "eventbridge" {
  source                 = "../../modules/eventbridge"
  name                   = local.name
  notification_queue_arn = module.sqs.notification_dispatch_queue_arn
  alerts_sns_topic_arn   = aws_sns_topic.alerts.arn
  tags                   = local.common_tags
}

module "backup" {
  source            = "../../modules/backup"
  name              = local.name
  rds_instance_arns = ["arn:aws:rds:${var.aws_region}:${data.aws_caller_identity.current.account_id}:db:${module.rds.db_instance_id}"]

  alarm_sns_topic_arns     = [aws_sns_topic.alerts.arn]
  backup_copy_region       = var.dr_region    # Cross-region DR copy
  enable_vault_lock        = true             # Prod: compliance vault lock
  vault_lock_changeable_days = 3              # 3-day grace period to correct config
  tags                     = local.common_tags
}

data "aws_caller_identity" "current" {}

resource "aws_secretsmanager_secret_version" "app_real" {
  secret_id = module.secrets.secret_arn

  secret_string = jsonencode({
    # Prod: connect via RDS Proxy for connection pooling + fast failover
    database_url       = "postgresql://lbro_app:${random_password.db.result}@${module.rds.proxy_endpoint}:5432/lbro"
    secret_key         = "REPLACE_WITH_STRONG_KEY_BEFORE_FIRST_DEPLOY"
    api_key            = "REPLACE_WITH_STRONG_API_KEY_BEFORE_FIRST_DEPLOY"
    sqs_queue_url      = module.sqs.incident_events_queue_url
    s3_evidence_bucket = module.s3.evidence_bucket_id
  })

  lifecycle { ignore_changes = [secret_string] }
  depends_on = [module.rds, module.sqs, module.s3]
}
