#!/usr/bin/env python3
"""LBRO Agent — lightweight log collection and event shipping daemon.

Capabilities:
  - Read application log files (configurable glob patterns)
  - Read nginx access/error logs
  - Read Apache access/error logs
  - Read Linux syslog (/var/log/syslog, /var/log/auth.log)
  - Buffer events in memory (configurable size)
  - Retry failed uploads with exponential backoff
  - Compress batches (gzip) when batch size >= compression_threshold
  - Authenticate using Project API Key
  - Ship to LBRO via /api/v1/events/batch

Configuration (via config file or environment variables):
  LBRO_API_KEY=proj_...
  LBRO_BASE_URL=https://your-lbro-instance.example.com
  LBRO_AGENT_APP_NAME=my-application
  LBRO_AGENT_LOG_FILES=/var/log/app/*.log,/var/log/nginx/access.log
  LBRO_AGENT_BATCH_SIZE=100
  LBRO_AGENT_FLUSH_INTERVAL=30
  LBRO_AGENT_SOURCE_IP=auto  # detect from hostname

Usage:
  python lbro_agent.py --config /etc/lbro/agent.conf
  python lbro_agent.py --api-key proj_xxx --log-files /var/log/app.log
  python lbro_agent.py --help
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

# ── Optional stdlib import for file tailing ──────────────────────────────────
try:
    import select as _select
    _HAS_SELECT = True
except ImportError:
    _HAS_SELECT = False

log = logging.getLogger("lbro_agent")

__version__ = "1.0.0"

# ─────────────────────────────────────────────────────────────────────────────
# Log parsers
# ─────────────────────────────────────────────────────────────────────────────

class LogParser:
    """Base class for log parsers."""
    name = "generic"

    def parse_line(self, line: str) -> dict | None:
        """Return a SecurityEvent-compatible dict or None to skip."""
        raise NotImplementedError


class NginxAccessLogParser(LogParser):
    name = "nginx"
    # Combined log format
    _RE = re.compile(
        r'(?P<ip>\S+) \S+ \S+ \[(?P<time>[^\]]+)\] '
        r'"(?P<method>\S+) (?P<path>\S+) \S+" (?P<status>\d+) (?P<size>\d+)'
    )

    def parse_line(self, line: str) -> dict | None:
        m = self._RE.match(line.strip())
        if not m:
            return None
        status = int(m.group("status"))
        event_type = "suspicious_request"
        severity = "info"
        if status == 401 or status == 403:
            event_type = "auth_failure"
            severity = "medium"
        elif status >= 500:
            event_type = "application_log"
            severity = "low"
        return {
            "event_type": event_type,
            "severity": severity,
            "source_ip": m.group("ip"),
            "message": f"HTTP {status} {m.group('method')} {m.group('path')}",
            "payload": {
                "http_method": m.group("method"),
                "http_path": m.group("path"),
                "http_status": status,
                "bytes": int(m.group("size")),
            },
        }


class SyslogParser(LogParser):
    name = "syslog"
    # Matches: Jul 13 12:00:00 hostname process[pid]: message
    _RE = re.compile(r"^\w+\s+\d+\s+\S+ \S+ (\S+)\[\d+\]: (.+)$")
    _SUSPICIOUS = {"sudo", "su", "ssh", "sshd", "pam_unix", "cron"}

    def parse_line(self, line: str) -> dict | None:
        m = self._RE.match(line.strip())
        if not m:
            return None
        process = m.group(1).lower()
        message = m.group(2)
        event_type = "system_log"
        severity = "info"
        if "failed" in message.lower() or "failure" in message.lower():
            event_type = "auth_failure"
            severity = "medium"
        elif process in self._SUSPICIOUS:
            event_type = "linux_audit"
            severity = "low"
        return {
            "event_type": event_type,
            "severity": severity,
            "message": message[:500],
            "payload": {"process": process, "raw_line": line.strip()[:1000]},
        }


class ApacheAccessLogParser(LogParser):
    name = "apache"
    # Combined log format (same as nginx)
    _RE = NginxAccessLogParser._RE

    def parse_line(self, line: str) -> dict | None:
        m = self._RE.match(line.strip())
        if not m:
            return None
        status = int(m.group("status"))
        severity = "info"
        event_type = "apache_log"
        if status == 401 or status == 403:
            event_type = "auth_failure"
            severity = "medium"
        return {
            "event_type": event_type,
            "severity": severity,
            "source_ip": m.group("ip"),
            "message": f"Apache HTTP {status} {m.group('method')} {m.group('path')}",
            "payload": {
                "http_status": status,
                "http_method": m.group("method"),
                "http_path": m.group("path"),
            },
        }


_PARSERS: dict[str, type[LogParser]] = {
    "nginx": NginxAccessLogParser,
    "apache": ApacheAccessLogParser,
    "syslog": SyslogParser,
    "generic": LogParser,
}


def detect_parser(path: str) -> LogParser:
    """Auto-detect log format from file path."""
    name = Path(path).name.lower()
    if "nginx" in name:
        return NginxAccessLogParser()
    if "apache" in name or "httpd" in name:
        return ApacheAccessLogParser()
    if "syslog" in name or "auth" in name or "kern" in name:
        return SyslogParser()
    return SyslogParser()  # fallback: treat as generic syslog-style


# ─────────────────────────────────────────────────────────────────────────────
# File tailer (follows file like `tail -F`)
# ─────────────────────────────────────────────────────────────────────────────

def tail_file(path: str, follow: bool = True) -> Iterator[str]:
    """Yield new lines from a file as they are written.

    Follows log rotation: detects inode change and reopens the file.
    """
    current_inode = None
    fh = None

    try:
        while True:
            try:
                stat = os.stat(path)
            except FileNotFoundError:
                time.sleep(1)
                continue

            # File rotated: inode changed
            if current_inode is not None and stat.st_ino != current_inode:
                if fh:
                    fh.close()
                fh = None

            if fh is None:
                try:
                    fh = open(path, "r", encoding="utf-8", errors="replace")
                    fh.seek(0, 2)  # seek to end for new events only
                    current_inode = stat.st_ino
                except OSError:
                    time.sleep(1)
                    continue

            while True:
                line = fh.readline()
                if not line:
                    if not follow:
                        return
                    time.sleep(0.1)
                    break
                yield line

    finally:
        if fh:
            fh.close()


# ─────────────────────────────────────────────────────────────────────────────
# Event buffer
# ─────────────────────────────────────────────────────────────────────────────

class EventBuffer:
    """Thread-safe ring buffer for security events."""

    def __init__(self, max_size: int = 10000):
        self._buf: deque = deque(maxlen=max_size)
        self._lock = threading.Lock()

    def push(self, event: dict) -> None:
        with self._lock:
            self._buf.append(event)

    def drain(self, max_count: int = 1000) -> list[dict]:
        """Remove and return up to max_count events."""
        with self._lock:
            batch = []
            while self._buf and len(batch) < max_count:
                batch.append(self._buf.popleft())
            return batch

    def __len__(self) -> int:
        with self._lock:
            return len(self._buf)


# ─────────────────────────────────────────────────────────────────────────────
# Agent
# ─────────────────────────────────────────────────────────────────────────────

class LBROAgent:
    """LBRO Agent — collects logs and ships events to LBRO."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8000",
        log_files: list[str] | None = None,
        source_application: str = "lbro-agent",
        source_ip: str | None = None,
        batch_size: int = 100,
        flush_interval: float = 30.0,
        max_retries: int = 5,
        retry_delay: float = 2.0,
        compression_threshold: int = 50,
    ):
        if not api_key.startswith("proj_"):
            raise ValueError("LBRO project API keys must start with 'proj_'")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._log_files = log_files or []
        self._source_application = source_application
        self._source_ip = source_ip
        self._batch_size = batch_size
        self._flush_interval = flush_interval
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._compression_threshold = compression_threshold
        self._buffer = EventBuffer(max_size=10 * batch_size)
        self._stop_event = threading.Event()
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        """Start the agent (blocking until stop() is called)."""
        log.info("LBRO Agent v%s starting — shipping to %s", __version__, self._base_url)

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, lambda *_: self.stop())
        signal.signal(signal.SIGTERM, lambda *_: self.stop())

        # Start a watcher thread per log file
        for path in self._log_files:
            t = threading.Thread(target=self._watch_file, args=(path,), daemon=True)
            t.start()
            self._threads.append(t)
            log.info("Watching %s", path)

        # Flush thread
        flush_t = threading.Thread(target=self._flush_loop, daemon=True)
        flush_t.start()
        self._threads.append(flush_t)

        log.info("Agent running. Ctrl+C to stop.")
        self._stop_event.wait()
        log.info("Flushing remaining events...")
        self._flush(force=True)
        log.info("Agent stopped.")

    def stop(self) -> None:
        self._stop_event.set()

    def _watch_file(self, path: str) -> None:
        parser = detect_parser(path)
        log.debug("Using %s parser for %s", parser.name, path)
        for line in tail_file(path, follow=True):
            if self._stop_event.is_set():
                break
            try:
                event = parser.parse_line(line)
                if event:
                    event.setdefault("source_application", self._source_application)
                    if self._source_ip:
                        event.setdefault("source_ip", self._source_ip)
                    event["source_agent_version"] = __version__
                    event["event_timestamp"] = datetime.now(timezone.utc).isoformat()
                    self._buffer.push(event)
            except Exception as exc:
                log.debug("Failed to parse line: %s", exc)

    def _flush_loop(self) -> None:
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._flush_interval)
            self._flush()

    def _flush(self, force: bool = False) -> None:
        while True:
            batch = self._buffer.drain(self._batch_size)
            if not batch:
                break
            self._ship_batch(batch)
            if not force or len(batch) < self._batch_size:
                break

    def _ship_batch(self, events: list[dict]) -> None:
        body = {"events": events}
        payload = json.dumps(body).encode("utf-8")

        # Compress large batches
        if len(events) >= self._compression_threshold:
            buf = io.BytesIO()
            with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
                gz.write(payload)
            payload = buf.getvalue()
            content_encoding = "gzip"
        else:
            content_encoding = None

        from urllib.request import Request as URLRequest, urlopen
        from urllib.error import HTTPError, URLError

        for attempt in range(self._max_retries + 1):
            try:
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": f"lbro-agent/{__version__}",
                }
                if content_encoding:
                    headers["Content-Encoding"] = content_encoding

                req = URLRequest(
                    self._base_url + "/api/v1/events/batch",
                    data=payload,
                    headers=headers,
                    method="POST",
                )
                with urlopen(req, timeout=30) as resp:
                    result = json.loads(resp.read())
                    log.info("Shipped %d events (accepted=%d rejected=%d)",
                             len(events), result.get("accepted", 0), result.get("rejected", 0))
                return

            except HTTPError as exc:
                log.error("Ship failed HTTP %s: %s", exc.code, exc.read()[:200])
                if exc.code in (401, 422):
                    return  # non-retryable
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * (2 ** attempt))
                    continue
            except (URLError, OSError) as exc:
                log.warning("Ship network error: %s", exc)
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay * (2 ** attempt))
                    continue

        log.error("Failed to ship batch of %d events after %d retries", len(events), self._max_retries)


# ─────────────────────────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=f"LBRO Agent v{__version__} — security log collection daemon"
    )
    parser.add_argument("--api-key", default=os.environ.get("LBRO_API_KEY"),
                        help="Project API key (env: LBRO_API_KEY)")
    parser.add_argument("--base-url", default=os.environ.get("LBRO_BASE_URL", "http://localhost:8000"),
                        help="LBRO base URL (env: LBRO_BASE_URL)")
    parser.add_argument("--log-files", default=os.environ.get("LBRO_AGENT_LOG_FILES", ""),
                        help="Comma-separated log file paths (env: LBRO_AGENT_LOG_FILES)")
    parser.add_argument("--app-name", default=os.environ.get("LBRO_AGENT_APP_NAME", "lbro-agent"),
                        help="Source application name (env: LBRO_AGENT_APP_NAME)")
    parser.add_argument("--source-ip", default=os.environ.get("LBRO_AGENT_SOURCE_IP"),
                        help="Source IP address (env: LBRO_AGENT_SOURCE_IP)")
    parser.add_argument("--batch-size", type=int,
                        default=int(os.environ.get("LBRO_AGENT_BATCH_SIZE", "100")))
    parser.add_argument("--flush-interval", type=float,
                        default=float(os.environ.get("LBRO_AGENT_FLUSH_INTERVAL", "30")))
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if not args.api_key:
        parser.error("--api-key or LBRO_API_KEY environment variable is required")

    log_files = [f.strip() for f in args.log_files.split(",") if f.strip()]

    agent = LBROAgent(
        api_key=args.api_key,
        base_url=args.base_url,
        log_files=log_files,
        source_application=args.app_name,
        source_ip=args.source_ip,
        batch_size=args.batch_size,
        flush_interval=args.flush_interval,
    )
    agent.start()


if __name__ == "__main__":
    main()
