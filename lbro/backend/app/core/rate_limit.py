"""
LBRO — Rate limiting
Uses slowapi (wraps limits library) with an in-process memory store for dev/single-instance,
and a Redis store in prod when REDIS_URL is set.

Per-endpoint limits (requests / window):

  POST /incidents                      60 / minute   — detectors fire fast; 60 is generous
                                       500 / hour    — hard ceiling prevents SQS flooding

  GET  /incidents                      120 / minute  — dashboard polling
  GET  /incidents/{id}                 120 / minute
  PATCH /incidents/{id}                30 / minute   — status updates are infrequent

  GET  /incidents/{id}/evidence        60 / minute
  GET  /incidents/{id}/evidence/{eid}/download
                                       10 / minute   — presigned URL generation is expensive

  GET  /incidents/{id}/notifications   60 / minute
  POST /incidents/{id}/notifications/{nid}/dispatch
                                       10 / minute   — regulatory dispatch is a one-shot action

  GET  /health                         exempt        — ALB probes must never be throttled
  GET  /health/ready                   exempt

Key is the client IP extracted from X-Forwarded-For (set by the ALB).
Falls back to the direct connection IP if the header is absent.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _get_client_ip(request: Request) -> str:
    """
    Extract the real client IP from X-Forwarded-For (set by ALB).
    ALB appends the client IP as the first value in the chain.
    Falls back to direct connection address for local dev.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # "client, proxy1, proxy2" — take the leftmost (originating client)
        return forwarded_for.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(key_func=_get_client_ip, default_limits=[])
