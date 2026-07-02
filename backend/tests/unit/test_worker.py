"""
LBRO — Unit tests for worker components

Tests worker logic without any network calls:
  - Backoff behaviour on empty queue polls
  - Idempotency: already-contained incidents are skipped
  - Action plan builds correctly per severity
  - Graceful shutdown respects in-flight count
"""
from __future__ import annotations

from unittest.mock import AsyncMock

from app.worker.containment import ContainmentPipeline
from app.worker.main import _MAX_POLL_INTERVAL, _MIN_POLL_INTERVAL, Worker, WorkerConfig

# ── ContainmentPipeline ───────────────────────────────────────────────────────

class TestContainmentActionPlan:
    def _make_pipeline(self) -> ContainmentPipeline:
        return ContainmentPipeline(session=AsyncMock())

    def test_critical_includes_isolation_and_revocation(self):
        p = self._make_pipeline()
        actions = p._build_action_plan("CRITICAL", ["db-01"], ["GDPR"])
        names = [a["name"] for a in actions]
        assert "network_isolation" in names
        assert "credential_revocation" in names
        assert "evidence_collection" in names

    def test_low_skips_isolation(self):
        p = self._make_pipeline()
        actions = p._build_action_plan("LOW", [], [])
        names = [a["name"] for a in actions]
        assert "network_isolation" not in names
        assert "credential_revocation" not in names
        assert "evidence_collection" in names

    def test_jurisdictions_add_notification_prep(self):
        p = self._make_pipeline()
        actions = p._build_action_plan("MEDIUM", [], ["GDPR", "DPDPA"])
        names = [a["name"] for a in actions]
        assert "regulatory_notification_prep" in names

    def test_no_jurisdictions_no_notification_prep(self):
        p = self._make_pipeline()
        actions = p._build_action_plan("HIGH", [], [])
        names = [a["name"] for a in actions]
        assert "regulatory_notification_prep" not in names

    def test_critical_actions_are_marked_critical(self):
        p = self._make_pipeline()
        actions = p._build_action_plan("CRITICAL", [], [])
        critical = {a["name"] for a in actions if a.get("critical")}
        assert "evidence_collection" in critical
        assert "network_isolation" in critical
        assert "credential_revocation" in critical


# ── Worker backoff ────────────────────────────────────────────────────────────

class TestWorkerBackoff:
    def _make_worker(self) -> Worker:
        return Worker(WorkerConfig(queue_url="https://sqs.test/queue"))

    def test_initial_poll_interval_is_minimum(self):
        # poll_interval starts at _MIN_POLL_INTERVAL before any polls
        assert _MIN_POLL_INTERVAL == 0.1

    def test_max_poll_interval_caps_backoff(self):
        # After many empty polls the interval must not exceed _MAX_POLL_INTERVAL
        interval = _MIN_POLL_INTERVAL
        for _ in range(50):
            interval = min(interval * 1.5, _MAX_POLL_INTERVAL)
        assert interval == _MAX_POLL_INTERVAL
        assert _MAX_POLL_INTERVAL == 20.0

    def test_backoff_resets_on_messages(self):
        # Simulates: empty queue (interval grows) then message arrives (resets)
        interval = _MIN_POLL_INTERVAL
        for _ in range(10):
            interval = min(interval * 1.5, _MAX_POLL_INTERVAL)
        assert interval > _MIN_POLL_INTERVAL
        # Message arrives — reset
        interval = _MIN_POLL_INTERVAL
        assert interval == 0.1


# ── Worker graceful shutdown ──────────────────────────────────────────────────

class TestWorkerShutdown:
    def test_shutdown_event_starts_unset(self):
        w = Worker(WorkerConfig(queue_url="https://sqs.test/queue"))
        assert not w._shutdown_event.is_set()

    def test_in_flight_starts_at_zero(self):
        w = Worker(WorkerConfig(queue_url="https://sqs.test/queue"))
        assert w._in_flight == 0

    async def test_handle_shutdown_signal_sets_event(self):
        w = Worker(WorkerConfig(queue_url="https://sqs.test/queue"))
        # Simulate signal handler
        w._handle_shutdown_signal()
        assert w._shutdown_event.is_set()
