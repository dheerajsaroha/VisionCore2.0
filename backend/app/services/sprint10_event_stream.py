"""
sprint10_event_stream.py — Enterprise Event Streaming & Dead Letter Queue (DLQ) Service
Sprint 10 — Enterprise Integrations, Event Streaming, External Webhooks & API Gateway Optimization

Provides:
- Event stream subscription management & routing
- Event replay capability for missed domain events
- DLQ inspection and retry processing
- Event stream stats and filtering by tenant/event_type
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from app.services.event_bus import event_bus, EventMessage

logger = logging.getLogger(__name__)


class EventStreamingService:
    """
    Enterprise Event Streaming & DLQ Management Service.
    Wraps and extends event_bus with stream replay, DLQ management, and multi-tenant telemetry.
    """

    def __init__(self):
        self._dlq_store: List[Dict[str, Any]] = []
        self._max_dlq_size: int = 5000

    def publish_stream_event(
        self,
        event_name: str,
        tenant_id: str,
        payload: Dict[str, Any],
        actor_id: Optional[int] = None,
        correlation_id: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Publish a stream event to event_bus and return structured envelope."""
        msg = event_bus.publish(
            event_name=event_name,
            tenant_id=tenant_id,
            payload=payload,
            actor_id=actor_id,
            correlation_id=correlation_id,
            headers=headers,
        )

        return {
            "event_id": msg.event_id,
            "event_name": msg.event_name,
            "tenant_id": msg.tenant_id,
            "actor_id": msg.actor_id,
            "correlation_id": msg.correlation_id,
            "timestamp": msg.timestamp,
            "payload": msg.payload,
            "retry_count": msg.retry_count,
            "status": "PUBLISHED",
        }

    def get_event_history(
        self,
        tenant_id: str,
        event_name: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Retrieve recent tenant-scoped event stream history."""
        results = []
        for msg in reversed(event_bus._history):
            if msg.tenant_id != tenant_id:
                continue
            if event_name and msg.event_name != event_name:
                continue

            results.append({
                "event_id": msg.event_id,
                "event_name": msg.event_name,
                "tenant_id": msg.tenant_id,
                "actor_id": msg.actor_id,
                "correlation_id": msg.correlation_id,
                "timestamp": msg.timestamp,
                "payload": msg.payload,
                "retry_count": msg.retry_count,
            })

            if len(results) >= limit:
                break

        return results

    def record_dlq_event(self, event_msg: EventMessage, error_reason: str) -> Dict[str, Any]:
        """Record a failed event message in the Dead Letter Queue."""
        entry = {
            "dlq_id": f"dlq-{len(self._dlq_store) + 1}",
            "event_id": event_msg.event_id,
            "event_name": event_msg.event_name,
            "tenant_id": event_msg.tenant_id,
            "actor_id": event_msg.actor_id,
            "correlation_id": event_msg.correlation_id,
            "payload": event_msg.payload,
            "error_reason": error_reason,
            "retry_count": event_msg.retry_count,
            "queued_at": datetime.now(timezone.utc).isoformat(),
            "status": "QUEUED",
        }

        self._dlq_store.append(entry)
        if len(self._dlq_store) > self._max_dlq_size:
            self._dlq_store = self._dlq_store[-self._max_dlq_size:]

        logger.warning(f"Recorded DLQ entry {entry['dlq_id']} for event {event_msg.event_id}: {error_reason}")
        return entry

    def get_dlq_messages(self, tenant_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get DLQ messages for an organization."""
        messages = [msg for msg in self._dlq_store if msg["tenant_id"] == tenant_id]
        return sorted(messages, key=lambda m: m["queued_at"], reverse=True)[:limit]

    def replay_dlq_message(self, tenant_id: str, dlq_id: str) -> Optional[Dict[str, Any]]:
        """Replay a DLQ message back onto the event stream."""
        for entry in self._dlq_store:
            if entry["dlq_id"] == dlq_id and entry["tenant_id"] == tenant_id:
                # Re-publish
                replayed_msg = event_bus.publish(
                    event_name=entry["event_name"],
                    tenant_id=entry["tenant_id"],
                    payload=entry["payload"],
                    actor_id=entry["actor_id"],
                    correlation_id=f"replay-{entry['event_id']}",
                )

                entry["status"] = "REPLAYED"
                entry["replayed_at"] = datetime.now(timezone.utc).isoformat()

                logger.info(f"Replayed DLQ event {dlq_id} as new event {replayed_msg.event_id}")
                return entry

        return None

    def get_stream_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get summary metrics for event stream and DLQ for an organization."""
        tenant_events = [m for m in event_bus._history if m.tenant_id == tenant_id]
        tenant_dlq = [d for d in self._dlq_store if d["tenant_id"] == tenant_id and d["status"] == "QUEUED"]

        return {
            "tenant_id": tenant_id,
            "total_events_buffered": len(tenant_events),
            "active_dlq_count": len(tenant_dlq),
            "dlq_status": "WARNING" if len(tenant_dlq) > 0 else "HEALTHY",
        }


# Singleton
event_stream_service = EventStreamingService()
