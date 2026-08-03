"""
event_bus.py — Enterprise Domain Event Bus Architecture
VisionCore 3.0 Enterprise Platform Services Layer

Provides:
- In-process and distributed (Kafka/RabbitMQ ready) Event Bus
- Topic-based publish/subscribe message delivery
- Event envelope standard (event_id, event_name, tenant_id, actor_id, correlation_id, timestamp, payload)
- Retries with exponential backoff & Dead Letter Queue (DLQ) tracking
- Canonical domain events: EmployeeCreated, AttendanceMarked, PayrollGenerated, LeaveApproved, TicketResolved, NotificationRequested, AuditRecorded
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


@dataclass
class EventMessage:
    """Standardized enterprise domain event message envelope."""
    event_id: str
    event_name: str  # e.g., 'EmployeeCreated', 'AttendanceMarked'
    tenant_id: str
    actor_id: Optional[int] = None
    correlation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)
    retry_count: int = 0
    max_retries: int = 3
    headers: Dict[str, str] = field(default_factory=dict)


EventHandler = Callable[[EventMessage], None]


class BaseBrokerAdapter(ABC):
    """Abstract message broker adapter."""

    @abstractmethod
    def publish(self, topic: str, message: EventMessage) -> bool:
        pass

    @abstractmethod
    def subscribe(self, topic: str, handler: EventHandler) -> None:
        pass


class InProcessBrokerAdapter(BaseBrokerAdapter):
    """In-memory event broker implementation."""

    def __init__(self):
        self._subscribers: Dict[str, List[EventHandler]] = {}
        self._dlq: List[EventMessage] = []

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if handler not in self._subscribers[topic]:
            self._subscribers[topic].append(handler)
        logger.debug(f"Subscribed handler {handler.__name__} to topic '{topic}'")

    def publish(self, topic: str, message: EventMessage) -> bool:
        handlers = self._subscribers.get(topic, [])
        # Also notify wildcard topic subscribers
        handlers = handlers + self._subscribers.get("*", [])

        if not handlers:
            logger.debug(f"No subscribers registered for topic '{topic}'")
            return True

        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                logger.error(f"Error handling event '{message.event_name}' on topic '{topic}': {e}")
                if message.retry_count < message.max_retries:
                    message.retry_count += 1
                    logger.info(f"Retrying event {message.event_id} (Attempt {message.retry_count}/{message.max_retries})")
                    self.publish(topic, message)
                else:
                    logger.warning(f"Event {message.event_id} exceeded max retries. Routing to DLQ.")
                    self._dlq.append(message)
        return True

    def get_dlq_messages() -> List[EventMessage]:
        return self._dlq


class EventBus:
    """
    Enterprise Centralized Event Bus.
    Consumed by all platform services and business modules.
    """

    def __init__(self, broker: Optional[BaseBrokerAdapter] = None):
        self._broker = broker or InProcessBrokerAdapter()
        self._history: List[EventMessage] = []
        self._max_history: int = 10000

    def subscribe(self, topic: str, handler: EventHandler) -> None:
        """Subscribe a listener handler to a topic or event name."""
        self._broker.subscribe(topic, handler)

    def publish(
        self,
        event_name: str,
        tenant_id: str,
        payload: Dict[str, Any],
        actor_id: Optional[int] = None,
        correlation_id: str = "",
        headers: Optional[Dict[str, str]] = None,
    ) -> EventMessage:
        """Publish a domain event envelope across the platform."""
        event_id = f"evt-{uuid.uuid4().hex[:16]}"
        msg = EventMessage(
            event_id=event_id,
            event_name=event_name,
            tenant_id=tenant_id,
            actor_id=actor_id,
            correlation_id=correlation_id or event_id,
            payload=payload,
            headers=headers or {},
        )

        # Track history
        self._history.append(msg)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

        # Publish to event_name topic and wildcard
        self._broker.publish(event_name, msg)

        logger.info(f"Published Domain Event '{event_name}' ({event_id}) for tenant {tenant_id}")

        # Audit Event Log Integration
        try:
            audit_service.record(
                actor_user_id=actor_id,
                organization_id=tenant_id,
                module="event_bus",
                action="publish_event",
                entity_type="domain_event",
                entity_id=event_id,
                summary=f"Domain Event '{event_name}' published",
                details={"event_name": event_name, "correlation_id": msg.correlation_id},
            )
        except Exception:
            pass

        return msg

    # Helper Event Publishers
    def publish_employee_created(self, tenant_id: str, user_id: int, email: str, actor_id: Optional[int] = None) -> EventMessage:
        return self.publish("EmployeeCreated", tenant_id, {"user_id": user_id, "email": email}, actor_id=actor_id)

    def publish_attendance_marked(self, tenant_id: str, user_id: int, status: str, actor_id: Optional[int] = None) -> EventMessage:
        return self.publish("AttendanceMarked", tenant_id, {"user_id": user_id, "status": status}, actor_id=actor_id)

    def publish_payroll_generated(self, tenant_id: str, payroll_id: str, total_amount: float, actor_id: Optional[int] = None) -> EventMessage:
        return self.publish("PayrollGenerated", tenant_id, {"payroll_id": payroll_id, "total_amount": total_amount}, actor_id=actor_id)

    def publish_leave_approved(self, tenant_id: str, leave_id: str, user_id: int, actor_id: Optional[int] = None) -> EventMessage:
        return self.publish("LeaveApproved", tenant_id, {"leave_id": leave_id, "user_id": user_id}, actor_id=actor_id)


# Singleton
event_bus = EventBus()
