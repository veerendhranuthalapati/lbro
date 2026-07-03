"""AWS SQS service for async job queuing."""
from __future__ import annotations

import json
import uuid

import boto3

from app.config import settings


def _get_client():
    kwargs = {"region_name": settings.AWS_REGION}
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
    if settings.AWS_ACCESS_KEY_ID:
        kwargs["aws_access_key_id"] = settings.AWS_ACCESS_KEY_ID
        kwargs["aws_secret_access_key"] = settings.AWS_SECRET_ACCESS_KEY
    return boto3.client("sqs", **kwargs)


class SQSService:
    def __init__(self):
        self.client = _get_client()

    def send_message(self, queue_url: str, body: dict, delay_seconds: int = 0) -> str:
        response = self.client.send_message(
            QueueUrl=queue_url,
            MessageBody=json.dumps(body),
            DelaySeconds=delay_seconds,
            MessageGroupId="default" if "fifo" in queue_url.lower() else None,
            MessageDeduplicationId=str(uuid.uuid4()) if "fifo" in queue_url.lower() else None,
        )
        return response["MessageId"]

    def receive_messages(
        self, queue_url: str, max_messages: int = 10, wait_time: int = 20
    ) -> list[dict]:
        response = self.client.receive_message(
            QueueUrl=queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=wait_time,
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
        )
        return response.get("Messages", [])

    def delete_message(self, queue_url: str, receipt_handle: str) -> None:
        self.client.delete_message(QueueUrl=queue_url, ReceiptHandle=receipt_handle)

    def change_message_visibility(
        self, queue_url: str, receipt_handle: str, timeout: int = 300
    ) -> None:
        self.client.change_message_visibility(
            QueueUrl=queue_url,
            ReceiptHandle=receipt_handle,
            VisibilityTimeout=timeout,
        )

    def enqueue_incident(self, incident_id: str, action: str = "classify") -> str:
        if not settings.SQS_INCIDENT_QUEUE_URL:
            return ""
        return self.send_message(
            settings.SQS_INCIDENT_QUEUE_URL,
            {"incident_id": incident_id, "action": action},
        )

    def enqueue_notification(self, notification_id: str) -> str:
        if not settings.SQS_NOTIFICATION_QUEUE_URL:
            return ""
        return self.send_message(
            settings.SQS_NOTIFICATION_QUEUE_URL,
            {"notification_id": notification_id, "action": "send"},
        )


sqs_service = SQSService()
