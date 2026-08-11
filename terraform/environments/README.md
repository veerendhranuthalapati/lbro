# DEPRECATED — Do not use for deployment

This directory (`terraform/environments/dev/` and `terraform/environments/prod/`) is **not** the canonical LBRO production Terraform path.

## Why deprecated

1. **Module API mismatch** — These configs call modules with arguments (`name`, `worker_task_role_arn`, `containment_actions_queue_arn`, etc.) that the current `terraform/modules/*` implementations do not accept.
2. **Missing / broken modules** — Expects a monolithic `modules/secrets` JSON secret shape; the canonical root uses inline Secrets Manager resources in `terraform/main.tf`.
3. **Region inconsistency** — Hardcodes `ap-south-1` for state backend and default `aws_region`, while README and canonical root default to `us-east-1`.
4. **Does not validate** — `terraform init` / `terraform validate` fail due to syntax errors and unsupported module arguments.

## Canonical path

Use **`terraform/`** (repository root `terraform/main.tf`). See [../README.md](../README.md).

## If you need environment-specific roots

Fork the canonical `terraform/main.tf` pattern and pass `-var="environment=production"` (or `staging` / `development`) rather than maintaining a separate directory tree.
