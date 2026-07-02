#!/bin/bash
# LocalStack initialization — creates S3 buckets and SQS queues for local dev

set -e

echo "==> LBRO: Initialising LocalStack resources..."

AWS="aws --endpoint-url=http://localhost:4566 --region=us-east-1"

# S3 buckets
$AWS s3 mb s3://lbro-evidence --region us-east-1 2>/dev/null || true
$AWS s3 mb s3://lbro-reports --region us-east-1 2>/dev/null || true

# Enable versioning on evidence bucket (for immutability)
$AWS s3api put-bucket-versioning \
  --bucket lbro-evidence \
  --versioning-configuration Status=Enabled 2>/dev/null || true

# SQS queues
$AWS sqs create-queue --queue-name lbro-incidents 2>/dev/null || true
$AWS sqs create-queue --queue-name lbro-notifications 2>/dev/null || true
$AWS sqs create-queue --queue-name lbro-dlq 2>/dev/null || true

# Set DLQ on incident queue (4 retries)
INCIDENT_ARN=$($AWS sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/lbro-incidents \
  --attribute-names QueueArn | python3 -c "import sys,json; print(json.load(sys.stdin)['Attributes']['QueueArn'])")

DLQ_ARN=$($AWS sqs get-queue-attributes \
  --queue-url http://localhost:4566/000000000000/lbro-dlq \
  --attribute-names QueueArn | python3 -c "import sys,json; print(json.load(sys.stdin)['Attributes']['QueueArn'])")

$AWS sqs set-queue-attributes \
  --queue-url http://localhost:4566/000000000000/lbro-incidents \
  --attributes "{\"RedrivePolicy\":\"{\\\"deadLetterTargetArn\\\":\\\"$DLQ_ARN\\\",\\\"maxReceiveCount\\\":\\\"4\\\"}\"}" 2>/dev/null || true

echo "==> LBRO: LocalStack resources ready"
echo "  S3:  lbro-evidence, lbro-reports"
echo "  SQS: lbro-incidents, lbro-notifications, lbro-dlq"
