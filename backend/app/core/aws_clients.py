"""
LBRO — AWS client singletons
boto3 clients are thread-safe and expensive to construct (TLS, config load).
Create once at module level and reuse across all requests.
"""
from __future__ import annotations

from typing import Any

import boto3

from app.config import settings

_sqs: Any = None
_s3: Any = None
_secrets: Any = None
_cloudwatch: Any = None


def get_sqs() -> Any:
    global _sqs
    if _sqs is None:
        _sqs = boto3.client("sqs", region_name=settings.AWS_REGION)
    return _sqs


def get_s3() -> Any:
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3", region_name=settings.AWS_REGION)
    return _s3


def get_secrets() -> Any:
    global _secrets
    if _secrets is None:
        _secrets = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
    return _secrets


def get_cloudwatch() -> Any:
    global _cloudwatch
    if _cloudwatch is None:
        _cloudwatch = boto3.client("cloudwatch", region_name=settings.AWS_REGION)
    return _cloudwatch


def reset_clients() -> None:
    """Reset all singletons — used in tests that need a fresh boto3 state."""
    global _sqs, _s3, _secrets, _cloudwatch
    _sqs = _s3 = _secrets = _cloudwatch = None
