# LBRO Terraform — Production Deployment

## Canonical production path

**Use `terraform/` (this directory) — NOT `terraform/environments/*`.**

```bash
cd terraform
terraform init \
  -backend-config="bucket=YOUR_TFSTATE_BUCKET" \
  -backend-config="key=lbro/terraform.tfstate" \
  -backend-config="region=us-east-1" \
  -backend-config="dynamodb_table=lbro-tfstate-lock"

terraform plan \
  -var="environment=production" \
  -var="api_image=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest" \
  -var="worker_image=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/lbro-api:latest" \
  -var="frontend_image=ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/lbro-frontend:latest" \
  -var="app_secret_key=$(openssl rand -hex 32)"
```

See [README.md](../README.md) for full AWS deployment steps.

## Layout

| Component | Module / resource |
|-----------|-------------------|
| Networking | `modules/networking` (VPC, subnets, NAT, IGW) |
| Secrets | Inline in `main.tf` (Secrets Manager + random DB password) |
| IAM | `modules/iam` (ECS execution + task roles) |
| SQS | `modules/sqs` (incidents, notifications, DLQ) |
| S3 | `modules/s3` (evidence, reports, ML models) |
| ECS | `modules/ecs` (API, worker, frontend, ALB) |
| RDS | `modules/rds` (PostgreSQL in private subnets) |
| Monitoring | `modules/monitoring` (CloudWatch alarms) |

## AWS region

Default provider region: **`us-east-1`** (`variables.tf`). Override with `-var="aws_region=..."`.

State backend region is configured at `terraform init` time via `-backend-config` (not hardcoded in `main.tf`).

## Obsolete paths

`terraform/environments/dev/` and `terraform/environments/prod/` are **deprecated stubs** from an alternate layout. They reference module APIs (`name`, `vpc`, `secrets` JSON blob) that do not match the current modules and **will not validate**. Do not use them for deployment.

Modules only used by the deprecated layout (`vpc`, `secrets`, `waf`, `backup`, `eventbridge`) are not wired into the canonical root stack.

## Validation (local, no AWS)

```bash
cd terraform
terraform init -backend=false
terraform validate
terraform fmt -check -recursive
```
