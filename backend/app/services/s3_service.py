"""AWS S3 service for evidence vault."""
from __future__ import annotations

import hashlib
import io
from typing import BinaryIO

import boto3
from botocore.exceptions import ClientError

from app.config import settings


def _get_client():
    kwargs = {
        "region_name": settings.AWS_REGION,
    }
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("s3", **kwargs)


class S3Service:
    def __init__(self):
        self.client = _get_client()

    def upload_file(
        self,
        bucket: str,
        key: str,
        data: bytes,
        content_type: str = "application/octet-stream",
        metadata: dict | None = None,
    ) -> str:
        """Upload bytes to S3, return the s3 key."""
        extra = {"ContentType": content_type}
        if metadata:
            extra["Metadata"] = {k: str(v) for k, v in metadata.items()}

        self.client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            **extra,
        )
        return key

    def generate_presigned_url(
        self,
        bucket: str,
        key: str,
        expiry: int = None,
        operation: str = "get_object",
    ) -> str:
        expiry = expiry or settings.S3_PRESIGNED_URL_EXPIRY
        return self.client.generate_presigned_url(
            operation,
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expiry,
        )

    def delete_object(self, bucket: str, key: str) -> None:
        self.client.delete_object(Bucket=bucket, Key=key)

    def object_exists(self, bucket: str, key: str) -> bool:
        try:
            self.client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError:
            return False

    def ensure_bucket(self, bucket: str) -> None:
        try:
            self.client.head_bucket(Bucket=bucket)
        except ClientError:
            if settings.AWS_REGION == "us-east-1":
                self.client.create_bucket(Bucket=bucket)
            else:
                self.client.create_bucket(
                    Bucket=bucket,
                    CreateBucketConfiguration={"LocationConstraint": settings.AWS_REGION},
                )
            # Enable versioning for evidence immutability
            self.client.put_bucket_versioning(
                Bucket=bucket,
                VersioningConfiguration={"Status": "Enabled"},
            )


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


s3_service = S3Service()
