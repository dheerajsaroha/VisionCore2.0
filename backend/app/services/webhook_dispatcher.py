"""
webhook_dispatcher.py — Enterprise Webhook Dispatcher
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Async webhook dispatch with retry logic
- HMAC-SHA256 request signing
- Event de-duplication
- Delivery tracking
- Dead letter queue for failed deliveries
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import aiohttp
import requests

from app.schema.integration import IntegrationEvent, WebhookEvent

logger = logging.getLogger(__name__)


class WebhookDispatcher:
    """
    Enterprise webhook dispatcher.

    Features:
    - Async dispatch with configurable timeout
    - Automatic retry with exponential backoff
    - HMAC-SHA256 signing for payload integrity
    - Event de-duplication within a configurable window
    - Dead letter queue for unrecoverable failures
    - Delivery tracking and analytics
    """

    def __init__(self):
        self._dead_letter_queue: list[dict] = []
        self._delivery_tracking: dict[str, dict] = {}
        self._seen_events: dict[str, float] = {}
        self._dedup_window_seconds: int = 300  # 5 minutes
        self._max_dead_letter: int = 1000
        self._max_delivery_tracking: int = 10000

    # =========================================================================
    #  Dispatch
    # =========================================================================

    async def dispatch_async(
        self,
        url: str,
        event: IntegrationEvent,
        secret: str = "",
        headers: Optional[dict[str, str]] = None,
        method: str = "POST",
        timeout: int = 30,
        max_retries: int = 3,
        retry_delay: int = 60,
    ) -> dict:
        """
        Dispatch an event asynchronously with retry logic.

        Returns delivery result dict.
        """
        # Check de-duplication
        dedup_key = f"{url}:{event.event_type}:{hashlib.md5(json.dumps(event.payload, default=str).encode()).hexdigest()}"
        if dedup_key in self._seen_events:
            elapsed = time.time() - self._seen_events[dedup_key]
            if elapsed < self._dedup_window_seconds:
                logger.debug(f"Duplicate event suppressed: {dedup_key} ({elapsed:.0f}s ago)")
                return {
                    "status": "duplicate_suppressed",
                    "event_type": event.event_type,
                    "url": url,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        self._seen_events[dedup_key] = time.time()

        # Build payload
        delivery_id = f"del-{uuid.uuid4().hex[:12]}"
        body = json.dumps({
            "event_type": event.event_type,
            "source_module": event.source_module,
            "source_id": event.source_id,
            "organization_id": event.organization_id,
            "priority": event.priority,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "delivery_id": delivery_id,
        }, default=str)

        # Build headers
        request_headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event.event_type,
            "X-Delivery-ID": delivery_id,
            "X-Timestamp": str(int(time.time())),
            "User-Agent": "VisionCore-Webhook/2.0",
        }

        if headers:
            request_headers.update(headers)

        # HMAC signing
        if secret:
            signature = hmac.new(
                secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Attempt delivery with retries
        attempt = 0
        last_error = None

        while attempt <= max_retries:
            attempt += 1
            start_time = time.time()

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        method=method,
                        url=url,
                        data=body,
                        headers=request_headers,
                        timeout=aiohttp.ClientTimeout(total=timeout),
                    ) as response:
                        duration_ms = (time.time() - start_time) * 1000
                        response_body = await response.text()

                        result = {
                            "delivery_id": delivery_id,
                            "event_type": event.event_type,
                            "url": url,
                            "method": method,
                            "status": "success" if response.ok else "failed",
                            "status_code": response.status,
                            "attempt": attempt,
                            "duration_ms": round(duration_ms, 2),
                            "error": None if response.ok else f"HTTP {response.status}",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }

                        if response.ok:
                            logger.info(
                                f"Webhook dispatched: {delivery_id} "
                                f"({event.event_type}) → {url} "
                                f"in {duration_ms:.0f}ms"
                            )
                            self._track_delivery(delivery_id, result)
                            return result

                        logger.warning(
                            f"Webhook attempt {attempt}/{max_retries + 1} failed: "
                            f"{url} ({response.status})"
                        )
                        last_error = f"HTTP {response.status}"

            except asyncio.TimeoutError:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Webhook timeout (attempt {attempt}/{max_retries + 1}): {url}"
                )
                last_error = "timeout"

                if attempt <= max_retries:
                    await asyncio.sleep(retry_delay * (2 ** (attempt - 1)))  # Exponential backoff
                    continue

            except aiohttp.ClientError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Webhook client error (attempt {attempt}/{max_retries + 1}): {e}"
                )
                last_error = str(e)

                if attempt <= max_retries:
                    await asyncio.sleep(retry_delay * (2 ** (attempt - 1)))
                    continue

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Webhook unexpected error: {e}")
                last_error = str(e)
                break

        # All retries exhausted - send to dead letter queue
        dead_letter_entry = {
            "delivery_id": delivery_id,
            "event_type": event.event_type,
            "url": url,
            "payload": event.payload,
            "error": last_error or "max_retries_exhausted",
            "attempts": attempt,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self._dead_letter_queue.append(dead_letter_entry)
        if len(self._dead_letter_queue) > self._max_dead_letter:
            self._dead_letter_queue = self._dead_letter_queue[-self._max_dead_letter:]

        result = {
            "delivery_id": delivery_id,
            "event_type": event.event_type,
            "url": url,
            "method": method,
            "status": "dead_letter",
            "status_code": None,
            "attempt": attempt,
            "duration_ms": round((time.time() - start_time) * 1000, 2),
            "error": last_error or "max_retries_exhausted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        logger.error(
            f"Webhook moved to dead letter queue: {delivery_id} → {url}: {last_error}"
        )
        self._track_delivery(delivery_id, result)
        return result

    def dispatch_sync(
        self,
        url: str,
        event: IntegrationEvent,
        secret: str = "",
        headers: Optional[dict[str, str]] = None,
        method: str = "POST",
        timeout: int = 30,
        max_retries: int = 3,
    ) -> dict:
        """
        Dispatch an event synchronously. Useful for testing or when
        async is not available.
        """
        delivery_id = f"del-{uuid.uuid4().hex[:12]}"
        body = json.dumps({
            "event_type": event.event_type,
            "source_module": event.source_module,
            "source_id": event.source_id,
            "organization_id": event.organization_id,
            "priority": event.priority,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "delivery_id": delivery_id,
        }, default=str)

        request_headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event.event_type,
            "X-Delivery-ID": delivery_id,
            "X-Timestamp": str(int(time.time())),
            "User-Agent": "VisionCore-Webhook/2.0",
        }

        if headers:
            request_headers.update(headers)

        if secret:
            signature = hmac.new(
                secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            request_headers["X-Webhook-Signature"] = f"sha256={signature}"

        attempt = 0
        while attempt <= max_retries:
            attempt += 1
            start_time = time.time()

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    data=body,
                    headers=request_headers,
                    timeout=timeout,
                )
                duration_ms = (time.time() - start_time) * 1000

                result = {
                    "delivery_id": delivery_id,
                    "event_type": event.event_type,
                    "url": url,
                    "method": method,
                    "status": "success" if response.ok else "failed",
                    "status_code": response.status_code,
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 2),
                    "error": None if response.ok else f"HTTP {response.status_code}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if response.ok:
                    return result

                if attempt > max_retries:
                    break
                time.sleep(60 * (2 ** (attempt - 1)))

            except Exception as e:
                if attempt > max_retries:
                    return {
                        "delivery_id": delivery_id,
                        "event_type": event.event_type,
                        "url": url,
                        "method": method,
                        "status": "failed",
                        "attempt": attempt,
                        "error": str(e),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                time.sleep(60 * (2 ** (attempt - 1)))

        return {
            "delivery_id": delivery_id,
            "event_type": event.event_type,
            "url": url,
            "method": method,
            "status": "failed",
            "attempt": attempt,
            "error": "max_retries_exhausted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # =========================================================================
    #  HMAC Verification
    # =========================================================================

    def verify_signature(
        self,
        payload: bytes,
        signature: str,
        secret: str,
    ) -> bool:
        """
        Verify an HMAC-SHA256 webhook signature.

        Used by inbound webhook receivers to verify request authenticity.
        """
        expected = hmac.new(
            secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(f"sha256={expected}", signature)

    # =========================================================================
    #  Dead Letter Queue
    # =========================================================================

    def get_dead_letter_queue(self, limit: int = 50) -> list[dict]:
        """Get entries from the dead letter queue."""
        return sorted(
            self._dead_letter_queue,
            key=lambda x: x["timestamp"],
            reverse=True,
        )[:limit]

    def retry_dead_letter(self, delivery_id: str) -> Optional[dict]:
        """Retry a dead letter delivery."""
        for entry in self._dead_letter_queue:
            if entry["delivery_id"] == delivery_id:
                self._dead_letter_queue.remove(entry)

                # Reconstruct event
                event = IntegrationEvent(
                    event_type=entry["event_type"],
                    source_module="webhook_dispatcher",
                    source_id=delivery_id,
                    organization_id=entry.get("payload", {}).get("organization_id", ""),
                    payload=entry["payload"],
                )

                # Re-dispatch synchronously
                return self.dispatch_sync(
                    url=entry["url"],
                    event=event,
                )

        return None

    def clear_dead_letter_queue(self) -> int:
        """Clear the dead letter queue. Returns count removed."""
        count = len(self._dead_letter_queue)
        self._dead_letter_queue = []
        return count

    # =========================================================================
    #  Tracking & Analytics
    # =========================================================================

    def _track_delivery(self, delivery_id: str, result: dict) -> None:
        """Track a delivery result."""
        self._delivery_tracking[delivery_id] = result
        if len(self._delivery_tracking) > self._max_delivery_tracking:
            # Remove oldest entries
            keys = sorted(
                self._delivery_tracking.keys(),
                key=lambda k: self._delivery_tracking[k].get("timestamp", ""),
            )[:len(self._delivery_tracking) - self._max_delivery_tracking]
            for k in keys:
                del self._delivery_tracking[k]

    def get_delivery_stats(self) -> dict:
        """Get delivery statistics."""
        deliveries = list(self._delivery_tracking.values())
        total = len(deliveries)
        success = len([d for d in deliveries if d.get("status") == "success"])
        failed = len([d for d in deliveries if d.get("status") in ("failed", "dead_letter")])
        dead_letter = len(self._dead_letter_queue)

        avg_duration = 0.0
        if total > 0:
            durations = [d.get("duration_ms", 0) for d in deliveries if d.get("duration_ms")]
            avg_duration = sum(durations) / len(durations) if durations else 0.0

        return {
            "total_deliveries": total,
            "successful": success,
            "failed": failed,
            "dead_letter_count": dead_letter,
            "success_rate": round((success / max(total, 1)) * 100, 1),
            "avg_duration_ms": round(avg_duration, 2),
            "tracked_events": len(self._seen_events),
        }

    def get_stats(self) -> dict:
        """Get dispatcher statistics."""
        return self.get_delivery_stats()


# Singleton
webhook_dispatcher = WebhookDispatcher()
