################################################################################
# LBRO — RDS Module (Scalability-enhanced)
#
# Scalability additions:
#   1. Read replica for offloading read queries (GET /incidents listing)
#   2. RDS Proxy for connection pooling — eliminates connection exhaustion at scale
#   3. Performance Insights with 7-day retention
#   4. Enhanced monitoring at 15s resolution
#   5. Auto minor version upgrades
################################################################################

################################################################################
# Security Group
################################################################################

resource "aws_security_group" "rds" {
  name        = "${var.name}-rds-sg"
  description = "RDS Postgres — allow from ECS tasks only"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_sg_ids
    description     = "Postgres from ECS tasks and RDS Proxy"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, { Name = "${var.name}-rds-sg" })
}

resource "aws_security_group" "rds_proxy" {
  name        = "${var.name}-rds-proxy-sg"
  description = "RDS Proxy — allow from ECS tasks, forward to RDS"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = var.allowed_sg_ids
    description     = "Postgres from ECS tasks"
  }

  egress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.rds.id]
    description     = "Forward to RDS"
  }

  tags = merge(var.tags, { Name = "${var.name}-rds-proxy-sg" })
}

################################################################################
# Parameter Group
################################################################################

resource "aws_db_parameter_group" "this" {
  name   = "${var.name}-pg16"
  family = "postgres16"

  parameter {
    name  = "log_connections"
    value = "1"
  }
  parameter {
    name  = "log_disconnections"
    value = "1"
  }
  parameter {
    name  = "log_min_duration_statement"
    value = "1000"
  }
  parameter {
    name  = "log_statement"
    value = "ddl"
  }
  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }
  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "pending-reboot"
  }
  # Connection pooling tuning — works alongside RDS Proxy
  parameter {
    name  = "max_connections"
    value = var.max_connections
  }

  tags = var.tags
}

################################################################################
# Enhanced Monitoring IAM Role
################################################################################

resource "aws_iam_role" "rds_monitoring" {
  name = "${var.name}-rds-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  managed_policy_arns = ["arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"]
  tags                = var.tags
}

################################################################################
# Primary RDS Instance
################################################################################

resource "aws_db_instance" "this" {
  identifier = "${var.name}-postgres"

  engine               = "postgres"
  engine_version       = "16.2"
  instance_class       = var.instance_class
  parameter_group_name = aws_db_parameter_group.this.name

  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage
  storage_type          = "gp3"
  storage_encrypted     = true
  kms_key_id            = var.kms_key_arn

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = var.db_subnet_group_name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false
  multi_az               = var.environment == "prod"

  backup_retention_period   = var.environment == "prod" ? 30 : 7
  backup_window             = "03:00-04:00"
  maintenance_window        = "sun:04:00-sun:05:00"
  copy_tags_to_snapshot     = true
  skip_final_snapshot       = var.environment != "prod"
  final_snapshot_identifier = "${var.name}-final-${formatdate("YYYYMMDD", timestamp())}"
  delete_automated_backups  = false

  # Enhanced monitoring at 15s for faster anomaly detection
  monitoring_interval = 15
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_arn
  performance_insights_retention_period = 7

  enabled_cloudwatch_logs_exports = ["postgresql", "upgrade"]

  deletion_protection        = var.environment == "prod"
  apply_immediately          = var.environment != "prod"
  auto_minor_version_upgrade = true

  tags = merge(var.tags, { Name = "${var.name}-postgres", Component = "database" })
}

################################################################################
# Read Replica — offloads GET /incidents listing queries from primary
################################################################################

resource "aws_db_instance" "replica" {
  count = var.create_read_replica ? 1 : 0

  identifier             = "${var.name}-postgres-replica"
  replicate_source_db    = aws_db_instance.this.identifier
  instance_class         = var.replica_instance_class
  parameter_group_name   = aws_db_parameter_group.this.name

  # Replica inherits storage, encryption, and subnet from primary
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = false

  monitoring_interval = 15
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  performance_insights_enabled          = true
  performance_insights_kms_key_id       = var.kms_key_arn
  performance_insights_retention_period = 7

  auto_minor_version_upgrade = true
  apply_immediately          = var.environment != "prod"
  skip_final_snapshot        = true

  tags = merge(var.tags, { Name = "${var.name}-postgres-replica", Component = "database-replica" })
}

################################################################################
# RDS Proxy — connection pooling
# Eliminates the Postgres connection limit bottleneck when ECS scales to many tasks.
# Each ECS task gets a proxy connection; the proxy maintains a small pool to RDS.
# Benefits: faster failover (35s → <1s), connection reuse, IAM auth support.
################################################################################

resource "aws_iam_role" "rds_proxy" {
  count = var.enable_rds_proxy ? 1 : 0

  name = "${var.name}-rds-proxy-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "rds.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = var.tags
}

resource "aws_iam_role_policy" "rds_proxy_secrets" {
  count = var.enable_rds_proxy ? 1 : 0

  name = "${var.name}-rds-proxy-secrets"
  role = aws_iam_role.rds_proxy[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [var.db_secret_arn]
      },
      {
        Effect   = "Allow"
        Action   = ["kms:Decrypt"]
        Resource = [var.kms_key_arn]
        Condition = {
          StringEquals = { "kms:ViaService" = "secretsmanager.${var.aws_region}.amazonaws.com" }
        }
      }
    ]
  })
}

resource "aws_db_proxy" "this" {
  count = var.enable_rds_proxy ? 1 : 0

  name                   = "${var.name}-proxy"
  debug_logging          = var.environment != "prod"
  engine_family          = "POSTGRESQL"
  idle_client_timeout    = 1800
  require_tls            = true
  role_arn               = aws_iam_role.rds_proxy[0].arn
  vpc_security_group_ids = [aws_security_group.rds_proxy.id]
  vpc_subnet_ids         = var.db_subnet_ids

  auth {
    auth_scheme               = "SECRETS"
    description               = "RDS master credentials"
    iam_auth                  = "DISABLED"
    secret_arn                = var.db_secret_arn
  }

  tags = merge(var.tags, { Name = "${var.name}-rds-proxy" })
}

resource "aws_db_proxy_default_target_group" "this" {
  count = var.enable_rds_proxy ? 1 : 0

  db_proxy_name = aws_db_proxy.this[0].name

  connection_pool_config {
    connection_borrow_timeout    = 120
    max_connections_percent      = 90   # Proxy uses up to 90% of max_connections
    max_idle_connections_percent = 50   # Keep 50% idle for burst headroom
  }
}

resource "aws_db_proxy_target" "this" {
  count = var.enable_rds_proxy ? 1 : 0

  db_instance_identifier = aws_db_instance.this.identifier
  db_proxy_name          = aws_db_proxy.this[0].name
  target_group_name      = aws_db_proxy_default_target_group.this[0].name
}

################################################################################
# CloudWatch Alarms
################################################################################

resource "aws_cloudwatch_metric_alarm" "cpu" {
  alarm_name          = "${var.name}-rds-cpu-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 3
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 80
  alarm_description   = "RDS CPU > 80% for 3 minutes"
  alarm_actions       = var.alarm_sns_topic_arns
  dimensions          = { DBInstanceIdentifier = aws_db_instance.this.identifier }
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "storage_low" {
  alarm_name          = "${var.name}-rds-storage-low"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = 1
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = 300
  statistic           = "Average"
  threshold           = 5368709120 # 5 GB
  alarm_description   = "RDS free storage < 5 GB"
  alarm_actions       = var.alarm_sns_topic_arns
  dimensions          = { DBInstanceIdentifier = aws_db_instance.this.identifier }
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "connections_high" {
  alarm_name          = "${var.name}-rds-connections-high"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "DatabaseConnections"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = var.max_connections_alarm_threshold
  alarm_description   = "RDS connection count critically high — check RDS Proxy health"
  alarm_actions       = var.alarm_sns_topic_arns
  dimensions          = { DBInstanceIdentifier = aws_db_instance.this.identifier }
  tags                = var.tags
}

resource "aws_cloudwatch_metric_alarm" "replica_lag" {
  count = var.create_read_replica ? 1 : 0

  alarm_name          = "${var.name}-rds-replica-lag"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = 2
  metric_name         = "ReplicaLag"
  namespace           = "AWS/RDS"
  period              = 60
  statistic           = "Average"
  threshold           = 30 # Alert if replica lags > 30s behind primary
  alarm_description   = "RDS replica lag > 30 seconds — reads may be stale"
  alarm_actions       = var.alarm_sns_topic_arns
  dimensions          = { DBInstanceIdentifier = aws_db_instance.this.identifier }
  tags                = var.tags
}
