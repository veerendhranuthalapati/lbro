#!/usr/bin/env bash
# Run once to create the S3 bucket + DynamoDB table for Terraform state
set -euo pipefail

ENV=${1:-dev}
REGION=${2:-ap-south-1}
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET="lbro-tf-state-${ENV}"
TABLE="lbro-tf-lock-${ENV}"

echo "Bootstrapping Terraform state for env=${ENV} in ${REGION}"

aws s3api create-bucket \
  --bucket "${BUCKET}" \
  --region "${REGION}" \
  --create-bucket-configuration LocationConstraint="${REGION}" 2>/dev/null || true

aws s3api put-bucket-versioning \
  --bucket "${BUCKET}" \
  --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
  --bucket "${BUCKET}" \
  --server-side-encryption-configuration '{
    "Rules": [{"ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"}}]
  }'

aws s3api put-public-access-block \
  --bucket "${BUCKET}" \
  --public-access-block-configuration \
    BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true

aws dynamodb create-table \
  --table-name "${TABLE}" \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region "${REGION}" 2>/dev/null || true

echo "Done. State bucket: s3://${BUCKET} | Lock table: ${TABLE}"
