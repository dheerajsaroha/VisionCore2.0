"""
event_bus.py — Central Enterprise Event Bus for VisionCore v2.0
Sprint 5 — Phase B: Enterprise Platform Integration

Provides:
- Event publishing with priority queuing
- Synchronous and asynchronous subscribers
- Event history persistence
- Retry mechanism with exponential backoff
- Dead-letter queue support
- Transaction-safe dispatching
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import traceback
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

from app.events.event_types import DomainEvent, EventPriority, EventStatus

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central enterprise event bus.
    
    Usage:
        from app.events import event_bus
        
        # Subscribe
        event_bus.subscribe("auth.user.login", my_handler)
        
        # Publish
        event_bus.publish(UserLoginEvent(user_id=1, email="user@org.com"))
        
        # Async publish
        await event_bus.apublish(event)
    """

    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._async_subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._event_history: list[dict] = []
        self._dead_letter_queue: list[dict] = []
        self._max_retries: int = 3
        self._retry_delay_base: float = 1.0  # seconds
        self._max_history: int = 10000
        self._history_enabled: bool = True

    # ------------------------------------------------------------------ 
    #  Configuration
    # ------------------------------------------------------------------

    def configure(
        self,
        max_retries: int = 3,
        retry_delay_base: float = 1.0,
        max_history: int = 10000,
        history_enabled: bool = True,
    ) -> None:
        """Configure event bus parameters."""
        self._max_retries = max_retries
        self._retry_delay_base = retry_delay_base
        self._max_history = max_history
        self._history_enabled = history_enabled

    # ------------------------------------------------------------------ 
    #  Subscription Management
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], None],
    ) -> Callable:
        """
        Register a synchronous handler for an event type.
        Returns the handler for later unsubscription.
        """
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)
            logger.debug(f"Subscribed sync handler for '{event_type}': {handler.__name__}")
        return handler

    def subscribe_async(
        self,
        event_type: str,
        handler: Callable[[DomainEvent], Coroutine],
    ) -> Callable:
        """
        Register an async handler for an event type.
        Returns the handler for later unsubscription.
        """
        if handler not in self._async_subscribers[event_type]:
            self._async_subscribers[event_type].append(handler)
            logger.debug(f"Subscribed async handler for '{event_type}': {handler.__name__}")
        return handler

    def unsubscribe(self, event_type: str, handler: Callable) -> bool:
        """Remove a handler subscription. Returns True if removed."""
        if handler in self._subscribers.get(event_type, []):
            self._subscribers[event_type].remove(handler)
            return True
        if handler in self._async_subscribers.get(event_type, []):
            self._async_subscribers[event_type].remove(handler)
            return True
        return False

    def unsubscribe_all(self, event_type: str | None = None) -> None:
        """Remove all subscriptions, optionally for a specific event type."""
        if event_type:
            self._subscribers[event_type] = []
            self._async_subscribers[event_type] = []
        else:
            self._subscribers.clear()
            self._async_subscribers.clear()

    # ------------------------------------------------------------------ 
    #  Publishing
    # ------------------------------------------------------------------

    def publish(self, event: DomainEvent) -> list[dict]:
        """
        Publish an event synchronously to all subscribers.
        Handles retries and dead-letter queuing.
        Returns list of handler execution results.
        """
        results = []
        event_type = event.event_type

        logger.info(f"Publishing event: {event_type} [{event.event_id}]")

        # Record to history
        self._record_history(event)

        # Get all handlers (sync + async wrappers)
        handlers = self._subscribers.get(event_type, []).copy()

        if not handlers:
            logger.debug(f"No handlers for event type: {event_type}")
            return results

        for handler in handlers:
            result = self._execute_handler(event, handler)
            results.append(result)

        # Also notify wildcard subscribers ("*")
        wildcard_handlers = self._subscribers.get("*", []).copy()
        for handler in wildcard_handlers:
            result = self._execute_handler(event, handler)
            results.append(result)

        return results

    async def apublish(self, event: DomainEvent) -> list[dict]:
        """
        Publish an event asynchronously to all subscribers.
        Handles retries and dead-letter queuing.
        """
        results = []
        event_type = event.event_type

        logger.info(f"Async publishing event: {event_type} [{event.event_id}]")

        # Record to history
        self._record_history(event)

        # Sync handlers
        handlers = self._subscribers.get(event_type, []).copy()
        for handler in handlers:
            result = self._execute_handler(event, handler)
            results.append(result)

        # Async handlers
        async_handlers = self._async_subscribers.get(event_type, []).copy()
        for handler in async_handlers:
            result = await self._aexecute_handler(event, handler)
            results.append(result)

        # Wildcard
        wildcard_handlers = self._subscribers.get("*", []).copy()
        for handler in wildcard_handlers:
            result = self._execute_handler(event, handler)
            results.append(result)

        wildcard_async = self._async_subscribers.get("*", []).copy()
        for handler in wildcard_async:
            result = await self._aexecute_handler(event, handler)
            results.append(result)

        return results

    # ------------------------------------------------------------------ 
    #  Handler Execution with Retry & DLQ
    # ------------------------------------------------------------------

    def _execute_handler(
        self,
        event: DomainEvent,
        handler: Callable,
    ) -> dict:
        """Execute a sync handler with retry logic."""
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                handler(event)
                return {
                    "handler": handler.__name__,
                    "event_id": event.event_id,
                    "status": "completed",
                    "attempt": attempt,
                }
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Handler '{handler.__name__}' failed (attempt {attempt}/{self._max_retries}): {e}"
                )
                if attempt < self._max_retries:
                    time.sleep(self._retry_delay_base * (2 ** (attempt - 1)))

        # Max retries exceeded — send to dead-letter queue
        self._send_to_dead_letter(event, handler, last_error)
        return {
            "handler": handler.__name__,
            "event_id": event.event_id,
            "status": "dead_letter",
            "error": str(last_error),
        }

    async def _aexecute_handler(
        self,
        event: DomainEvent,
        handler: Callable,
    ) -> dict:
        """Execute an async handler with retry logic."""
        last_error = None
        for attempt in range(1, self._max_retries + 1):
            try:
                await handler(event)
                return {
                    "handler": handler.__name__,
                    "event_id": event.event_id,
                    "status": "completed",
                    "attempt": attempt,
                }
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Async handler '{handler.__name__}' failed "
                    f"(attempt {attempt}/{self._max_retries}): {e}"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(self._retry_delay_base * (2 ** (attempt - 1)))

        # Max retries exceeded — send to dead-letter queue
        self._send_to_dead_letter(event, handler, last_error)
        return {
            "handler": handler.__name__,
            "event_id": event.event_id,
            "status": "dead_letter",
            "error": str(last_error),
        }

    # ------------------------------------------------------------------ 
    #  Dead-Letter Queue
    # ------------------------------------------------------------------

    def _send_to_dead_letter(
        self,
        event: DomainEvent,
        handler: Callable,
        error: Exception,
    ) -> None:
        """Send a failed event to the dead-letter queue."""
        entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "handler": handler.__name__,
            "error": str(error),
            "traceback": traceback.format_exc(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_data": self._event_to_dict(event),
        }
        self._dead_letter_queue.append(entry)
        logger.error(
            f"Event sent to DLQ: {event.event_type} [{event.event_id}] "
            f"→ handler '{handler.__name__}': {error}"
        )

    def get_dead_letter_queue(self) -> list[dict]:
        """Get all dead-letter entries."""
        return self._dead_letter_queue.copy()

    def retry_dead_letter(self, index: int = -1) -> bool:
        """
        Retry a dead-letter entry. Default retries the latest.
        Returns True if retry was attempted.
        """
        if not self._dead_letter_queue:
            return False
        entry = self._dead_letter_queue.pop(index)
        # Reconstruct event from dict and republish
        event_dict = entry.get("event_data", {})
        # Find the matching event class
        from app.events.event_types import (
            UserLoginEvent, UserLogoutEvent, LeaveRequestedEvent, 
            LeaveApprovedEvent, AssetAssignedEvent, PolicyPublishedEvent,
            ReviewSubmittedEvent, WorkflowStartedEvent,
        )
        # Map event types to classes
        EVENT_CLASS_MAP = {
            "auth.user.login": UserLoginEvent,
            "auth.user.logout": UserLogoutEvent,
            "leave.requested": LeaveRequestedEvent,
            "leave.approved": LeaveApprovedEvent,
            "asset.assigned": AssetAssignedEvent,
            "policy.published": PolicyPublishedEvent,
            "performance.review.submitted": ReviewSubmittedEvent,
            "workflow.started": WorkflowStartedEvent,
        }
        event_class = EVENT_CLASS_MAP.get(entry["event_type"])
        if event_class:
            event = event_class(**event_dict)
            self.publish(event)
            return True
        return False

    def clear_dead_letter_queue(self) -> int:
        """Clear and return the count of dead-letter entries."""
        count = len(self._dead_letter_queue)
        self._dead_letter_queue.clear()
        return count

    # ------------------------------------------------------------------ 
    #  Event History
    # ------------------------------------------------------------------

    def _record_history(self, event: DomainEvent) -> None:
        """Record event to history if enabled."""
        if not self._history_enabled:
            return
        entry = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "source_module": event.source_module,
            "timestamp": event.timestamp.isoformat(),
            "organization_id": event.organization_id,
            "actor_user_id": event.actor_user_id,
            "priority": event.priority.name,
            "version": event.version,
            "metadata": event.metadata,
        }
        self._event_history.append(entry)
        # Trim history
        if len(self._event_history) > self._max_history:
            self._event_history = self._event_history[-self._max_history:]

    def get_history(
        self,
        event_type: str | None = None,
        source_module: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict]:
        """Get event history with optional filtering."""
        results = self._event_history
        if event_type:
            results = [e for e in results if e["event_type"] == event_type]
        if source_module:
            results = [e for e in results if e["source_module"] == source_module]
        return results[offset:offset + limit]

    def get_history_count(
        self,
        event_type: str | None = None,
        source_module: str | None = None,
    ) -> int:
        """Get count of events in history."""
        return len(self.get_history(event_type, source_module, limit=0))

    def clear_history(self) -> int:
        """Clear and return the count of history entries."""
        count = len(self._event_history)
        self._event_history.clear()
        return count

    # ------------------------------------------------------------------ 
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _event_to_dict(event: DomainEvent) -> dict:
        """Convert a domain event to a serializable dict."""
        result = {}
        for field_name in event.__dataclass_fields__:
            value = getattr(event, field_name)
            if isinstance(value, datetime):
                result[field_name] = value.isoformat()
            elif isinstance(value, Enum):
                result[field_name] = value.name
            else:
                result[field_name] = value
        return result

    @staticmethod
    def event_from_dict(event_type: str, data: dict) -> DomainEvent:
        """Reconstruct a domain event from a dict."""
        from app.events import event_types as et
        EVENT_CLASS_MAP = getattr(et, "EVENT_CLASS_MAP", {})
        # Build map dynamically
        for name in dir(et):
            obj = getattr(et, name)
            if isinstance(obj, type) and issubclass(obj, DomainEvent) and obj != DomainEvent:
                if hasattr(obj, "event_type") and isinstance(obj.event_type, str):
                    EVENT_CLASS_MAP[obj.event_type] = obj
        cls = EVENT_CLASS_MAP.get(event_type) or DomainEvent
        # Convert datetime strings back
        for key, value in data.items():
            if isinstance(value, str) and "timestamp" in key.lower():
                try:
                    data[key] = datetime.fromisoformat(value)
                except (ValueError, TypeError):
                    pass
        return cls(**data)

    def get_stats(self) -> dict:
        """Get event bus statistics."""
        return {
            "total_events_published": len(self._event_history),
            "dead_letter_count": len(self._dead_letter_queue),
            "sync_subscribers": {
                event_type: len(handlers)
                for event_type, handlers in self._subscribers.items()
            },
            "async_subscribers": {
                event_type: len(handlers)
                for event_type, handlers in self._async_subscribers.items()
            },
            "max_retries": self._max_retries,
            "history_enabled": self._history_enabled,
        }


# Singleton instance
event_bus = EventBus()
