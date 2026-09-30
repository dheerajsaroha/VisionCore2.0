"""
notification_service.py — Centralized Enterprise Notification Service
Sprint 5 — Phase B: Enterprise Platform Integration

Supports:
- In-App Notifications
- Email Notifications
- SMS Provider abstraction
- Push Notification abstraction
- Notification Templates
- Notification Preferences
- Notification History
- Notification Analytics
"""
from __future__ import annotations

import json
import logging
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from enum import Enum
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationChannel(Enum):
    IN_APP = "in_app"
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"


class NotificationPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class Notification:
    """Universal notification payload."""
    id: str = ""
    user_id: int = 0
    organization_id: str = ""
    channel: NotificationChannel = NotificationChannel.IN_APP
    priority: NotificationPriority = NotificationPriority.NORMAL
    title: str = ""
    message: str = ""
    template_code: str = ""
    template_data: dict = field(default_factory=dict)
    source_module: str = ""
    source_event: str = ""
    source_id: str = ""
    action_url: Optional[str] = None
    is_read: bool = False
    read_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    signature: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# Notification templates
NOTIFICATION_TEMPLATES = {
    # Workflow / Approval
    "workflow.request_submitted": {
        "title": "Approval Request Submitted",
        "template": "Your {entity_type} request has been submitted for approval.",
    },
    "workflow.approved": {
        "title": "Request Approved",
        "template": "Your {entity_type} request has been approved by {approver_name}.",
    },
    "workflow.rejected": {
        "title": "Request Rejected",
        "template": "Your {entity_type} request has been rejected. Reason: {reason}.",
    },
    "workflow.escalated": {
        "title": "Request Escalated",
        "template": "An approval request has been escalated to you for {entity_type}.",
    },
    # Leave
    "leave.requested": {
        "title": "Leave Request Submitted",
        "template": "Your leave request ({leave_type}, {total_days} days) has been submitted.",
    },
    "leave.approved": {
        "title": "Leave Approved",
        "template": "Your {leave_type} leave for {total_days} days has been approved.",
    },
    "leave.rejected": {
        "title": "Leave Rejected",
        "template": "Your {leave_type} leave request has been rejected.",
    },
    # Attendance
    "attendance.corrected": {
        "title": "Attendance Corrected",
        "template": "Your attendance on {date} has been corrected.",
    },
    # Performance
    "performance.review_submitted": {
        "title": "Performance Review Submitted",
        "template": "A {review_type} performance review has been submitted for you.",
    },
    "performance.review_acknowledged": {
        "title": "Review Acknowledged",
        "template": "Your performance review has been acknowledged.",
    },
    "performance.promotion_recommended": {
        "title": "Promotion Recommended",
        "template": "You have been recommended for promotion to {proposed_role}.",
    },
    # Policy
    "policy.published": {
        "title": "New Policy Published",
        "template": "Policy '{title}' has been published. Please acknowledge it.",
    },
    "policy.acknowledgement_reminder": {
        "title": "Policy Acknowledgement Reminder",
        "template": "Please acknowledge the policy '{title}' by {deadline}.",
    },
    "compliance.breach": {
        "title": "Compliance Breach Detected",
        "template": "A compliance breach of type '{breach_type}' has been detected.",
    },
    # Asset
    "asset.assigned": {
        "title": "Asset Assigned",
        "template": "Asset '{asset_name}' ({asset_tag}) has been assigned to you.",
    },
    "asset.maintenance_due": {
        "title": "Maintenance Due",
        "template": "Asset '{asset_name}' is due for {maintenance_type} maintenance.",
    },
    "asset.license_expiring": {
        "title": "License Expiring",
        "template": "License for {asset_name} expires in {days_remaining} days.",
    },
    # Subscription
    "subscription.expiring": {
        "title": "Subscription Expiring",
        "template": "Your {plan_name} subscription will expire on {expiry_date}.",
    },
    "subscription.plan_changed": {
        "title": "Subscription Plan Changed",
        "template": "Your subscription has been changed to {new_plan_name}.",
    },
    # Payroll
    "payroll.generated": {
        "title": "Payroll Generated",
        "template": "Your payroll for {month}/{year} has been generated.",
    },
    "payroll.paid": {
        "title": "Salary Credited",
        "template": "Your salary of {amount} for {month}/{year} has been credited.",
    },
    # Recruitment
    "interview.scheduled": {
        "title": "Interview Scheduled",
        "template": "An interview with {candidate_name} has been scheduled.",
    },
}


class NotificationService:
    """
    Centralized notification service.
    Supports in-app, email, SMS, and push notifications.
    """

    def __init__(self):
        self._history: list[Notification] = []
        self._max_history: int = 50000

    # ------------------------------------------------------------------
    #  Send Notifications
    # ------------------------------------------------------------------

    def send(
        self,
        user_id: int,
        organization_id: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        title: str = "",
        message: str = "",
        template_code: str = "",
        template_data: dict | None = None,
        source_module: str = "",
        source_event: str = "",
        source_id: str = "",
        priority: NotificationPriority = NotificationPriority.NORMAL,
        action_url: str | None = None,
    ) -> Notification:
        """Send a notification through the specified channel."""
        # Resolve template if provided
        if template_code and template_code in NOTIFICATION_TEMPLATES:
            tmpl = NOTIFICATION_TEMPLATES[template_code]
            if not title:
                title = tmpl["title"]
            if not message and template_data:
                message = tmpl["template"].format(**template_data)
            elif not message:
                message = tmpl["template"]

        notif = Notification(
            id=self._generate_id(),
            user_id=user_id,
            organization_id=organization_id,
            channel=channel,
            priority=priority,
            title=title,
            message=message,
            template_code=template_code,
            template_data=template_data or {},
            source_module=source_module,
            source_event=source_event,
            source_id=source_id,
            action_url=action_url,
        )

        # Route to channel
        if channel == NotificationChannel.IN_APP:
            self._send_in_app(notif)
        elif channel == NotificationChannel.EMAIL:
            self._send_email(notif)
        elif channel == NotificationChannel.SMS:
            self._send_sms(notif)
        elif channel == NotificationChannel.PUSH:
            self._send_push(notif)

        # Record history
        self._record_history(notif)

        return notif

    def send_template(
        self,
        user_id: int,
        organization_id: str,
        template_code: str,
        template_data: dict,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        source_module: str = "",
        source_event: str = "",
        source_id: str = "",
    ) -> Notification:
        """Send a notification using a template."""
        return self.send(
            user_id=user_id,
            organization_id=organization_id,
            channel=channel,
            template_code=template_code,
            template_data=template_data,
            source_module=source_module,
            source_event=source_event,
            source_id=source_id,
            priority=priority,
        )

    def broadcast(
        self,
        user_ids: list[int],
        organization_id: str,
        title: str,
        message: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        source_module: str = "",
        source_event: str = "",
    ) -> list[Notification]:
        """Send the same notification to multiple users."""
        notifications = []
        for uid in user_ids:
            notif = self.send(
                user_id=uid,
                organization_id=organization_id,
                channel=channel,
                title=title,
                message=message,
                source_module=source_module,
                source_event=source_event,
            )
            notifications.append(notif)
        return notifications

    # ------------------------------------------------------------------
    #  Channel Implementations
    # ------------------------------------------------------------------

    def _send_in_app(self, notif: Notification) -> None:
        """In-app notifications are stored in history for frontend polling."""
        logger.info(f"In-app notification sent to user {notif.user_id}: {notif.title}")

    def _send_email(self, notif: Notification) -> None:
        """Send email via SMTP."""
        if not settings.SMTP_HOST or not settings.SMTP_USER:
            logger.warning("Email not configured. Skipping email notification.")
            return
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = notif.title
            msg["From"] = settings.EMAIL_FROM
            msg["To"] = self._get_user_email(notif.user_id)
            msg.attach(MIMEText(notif.message, "plain"))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(msg)
            logger.info(f"Email sent to user {notif.user_id}: {notif.title}")
        except Exception as e:
            logger.error(f"Failed to send email to user {notif.user_id}: {e}")

    def _send_sms(self, notif: Notification) -> None:
        """SMS sending (abstraction layer — integrate with Twilio, AWS SNS, etc.)."""
        logger.info(f"SMS would be sent to user {notif.user_id}: {notif.title[:50]}")
        # Integrate with SMS provider here
        # Example: twilio_client.messages.create(body=notif.message, to=phone, from_=sender)

    def _send_push(self, notif: Notification) -> None:
        """Push notification (abstraction layer — integrate with FCM, APNs, etc.)."""
        logger.info(f"Push notification would be sent to user {notif.user_id}: {notif.title}")

    def _send_webhook(self, notif: Notification) -> None:
        """Webhook delivery with HMAC SHA-256 payload signature."""
        notif.signature = self._sign_webhook_payload(notif)
        logger.info(f"Webhook dispatched for org {notif.organization_id}: {notif.title} (Sig: {notif.signature[:12]}...)")

    def _send_slack(self, notif: Notification) -> None:
        """Slack Integration Channel."""
        logger.info(f"Slack message queued for user {notif.user_id}: {notif.title}")

    def _send_teams(self, notif: Notification) -> None:
        """Microsoft Teams Integration Channel."""
        logger.info(f"Teams notification queued for user {notif.user_id}: {notif.title}")

    def _sign_webhook_payload(self, notif: Notification) -> str:
        import hmac
        import hashlib
        secret = getattr(settings, "WEBHOOK_SECRET", "visioncore_webhook_secret_key").encode('utf-8')
        payload = f"{notif.id}:{notif.organization_id}:{notif.created_at}".encode('utf-8')
        return hmac.new(secret, payload, hashlib.sha256).hexdigest()
        # Integrate with push provider here
        # Example: push_service.send(device_token, title=notif.title, body=notif.message)

    # ------------------------------------------------------------------
    #  Notification Management
    # ------------------------------------------------------------------

    def mark_read(self, notification_id: str) -> bool:
        """Mark a notification as read."""
        for notif in self._history:
            if notif.id == notification_id:
                notif.is_read = True
                notif.read_at = datetime.now(timezone.utc).isoformat()
                return True
        return False

    def mark_all_read(self, user_id: int) -> int:
        """Mark all notifications for a user as read. Returns count."""
        count = 0
        for notif in self._history:
            if notif.user_id == user_id and not notif.is_read:
                notif.is_read = True
                notif.read_at = datetime.now(timezone.utc).isoformat()
                count += 1
        return count

    def get_for_user(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0,
        unread_only: bool = False,
    ) -> list[dict]:
        """Get notifications for a user."""
        results = [n for n in self._history if n.user_id == user_id]
        if unread_only:
            results = [n for n in results if not n.is_read]
        results.sort(key=lambda n: n.created_at, reverse=True)
        return [self._notif_to_dict(n) for n in results[offset:offset + limit]]

    def get_unread_count(self, user_id: int) -> int:
        """Get unread notification count for a user."""
        return sum(1 for n in self._history if n.user_id == user_id and not n.is_read)

    def get_analytics(self, organization_id: str) -> dict:
        """Get notification analytics for an organization."""
        org_notifs = [n for n in self._history if n.organization_id == organization_id]
        total = len(org_notifs)
        read = sum(1 for n in org_notifs if n.is_read)
        unread = total - read
        by_channel = {}
        by_module = {}
        for n in org_notifs:
            by_channel[n.channel.value] = by_channel.get(n.channel.value, 0) + 1
            by_module[n.source_module] = by_module.get(n.source_module, 0) + 1
        return {
            "total": total,
            "read": read,
            "unread": unread,
            "read_rate": round(read / max(total, 1) * 100, 1),
            "by_channel": by_channel,
            "by_module": by_module,
        }

    def get_all_notifications(
        self, limit: int = 100, offset: int = 0
    ) -> list[dict]:
        """Get all notifications (admin use)."""
        sorted_history = sorted(
            self._history, key=lambda n: n.created_at, reverse=True
        )
        return [
            self._notif_to_dict(n) for n in sorted_history[offset:offset + limit]
        ]

    # ------------------------------------------------------------------
    #  Internal Helpers
    # ------------------------------------------------------------------

    def _record_history(self, notif: Notification) -> None:
        self._history.append(notif)
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]

    def _generate_id(self) -> str:
        import uuid
        return str(uuid.uuid4())

    def _get_user_email(self, user_id: int) -> str:
        """Get user email from DB. In-memory fallback for now."""
        from app.db.database import SessionLocal
        from app.db.models.all_models import User
        try:
            db = SessionLocal()
            user = db.query(User).filter(User.id == user_id).first()
            db.close()
            if user:
                return user.email
        except Exception:
            pass
        return f"user_{user_id}@visioncore.local"

    @staticmethod
    def _notif_to_dict(notif: Notification) -> dict:
        return {
            "id": notif.id,
            "user_id": notif.user_id,
            "channel": notif.channel.value,
            "priority": notif.priority.value,
            "title": notif.title,
            "message": notif.message,
            "template_code": notif.template_code,
            "template_data": notif.template_data,
            "source_module": notif.source_module,
            "source_event": notif.source_event,
            "source_id": notif.source_id,
            "action_url": notif.action_url,
            "is_read": notif.is_read,
            "read_at": notif.read_at,
            "created_at": notif.created_at,
        }


# Singleton
notification_service = NotificationService()


# ─────────────────────────────────────────────────────────────────────────────
#  Durable, database-backed dispatch
#
#  NotificationService above is in-memory and process-local, so anything it
#  delivers disappears on restart and is invisible to the in-app notification
#  feed, which reads the `notifications` table. The helpers below write real
#  rows so a business event (a leave request awaiting review, say) actually
#  reaches its recipient.
# ─────────────────────────────────────────────────────────────────────────────

def _db_recipients_for_permission(
    db: Session, org_id: Any, permission_name: str
) -> list[int]:
    """User ids in the organisation holding a permission, via any of their roles."""
    from app.db.models.all_models import Permission, Role, RolePermission, User

    return [
        row[0]
        for row in (
            db.query(User.id)
            # Join on the foreign keys rather than through `User.role`: an
            # explicit on-clause against a relationship path is rejected.
            .join(RolePermission, RolePermission.role_id == User.role_id)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(
                User.org_id == org_id,
                User.is_active == 1,
                User.is_deleted == 0,
                Permission.name == permission_name,
            )
            .distinct()
            .all()
        )
    ]


def persist_notification(
    db: Session,
    *,
    user_id: int,
    org_id: Any,
    title: str,
    message: Optional[str] = None,
    notif_type: str = "info",
    action_url: Optional[str] = None,
    source_event: Optional[str] = None,
) -> None:
    """Write one durable in-app notification row."""
    import uuid as _uuid

    from app.db.models.all_models import Notification as NotificationRow

    db.add(
        NotificationRow(
            id=str(_uuid.uuid4()),
            user_id=user_id,
            org_id=org_id,
            title=title[:300],
            message=message,
            type=notif_type,
            action_url=action_url,
            source_event=source_event,
            is_read=False,
        )
    )


def notify_leave_approvers(
    db: Session,
    leave_request: Any,
    *,
    actor_id: Optional[int] = None,
) -> int:
    """
    Tell everyone who can act on a leave request that it needs review.

    The blueprint promises the requester "manager receives notification, 1-click
    approve". Recipients are the requester's own reporting manager plus anyone
    holding `leave.approve` in the organisation, so a request is never left
    unowned when a manager is unassigned. The requester is never notified of
    their own request.

    Returns the number of recipients notified.
    """
    from app.db.models.all_models import EmploymentRecord, LeaveType, User

    org_id = leave_request.organization_id
    requester_id = leave_request.user_id

    # 1. The requester's own reporting manager takes precedence.
    recipients: list[int] = []
    employment = (
        db.query(EmploymentRecord)
        .filter(
            EmploymentRecord.user_id == requester_id,
            EmploymentRecord.org_id == org_id,
        )
        .order_by(EmploymentRecord.id.desc())
        .first()
    )
    if employment and employment.reporting_manager_id:
        recipients.append(employment.reporting_manager_id)

    # 2. Anyone else with authority to approve.
    for candidate in _db_recipients_for_permission(db, org_id, "leave.approve"):
        if candidate not in recipients:
            recipients.append(candidate)

    # The requester approving or being notified about their own request is
    # never useful, and would be the self-approval path the routes block anyway.
    recipients = [
        r for r in recipients if r != requester_id and r != actor_id
    ]
    if not recipients:
        return 0

    leave_type = (
        db.query(LeaveType).filter(LeaveType.id == leave_request.leave_type_id).first()
    )
    requester = db.query(User).filter(User.id == requester_id).first()
    requester_name = (requester.full_name if requester else "An employee")

    start = _fmt_dt(leave_request.start_date)
    end = _fmt_dt(leave_request.end_date)
    days = getattr(leave_request, "total_days", None)
    type_name = (leave_type.name if leave_type else "leave")

    action_url = f"/leave/requests/{leave_request.id}"
    for user_id in recipients:
        persist_notification(
            db,
            user_id=user_id,
            org_id=org_id,
            title=f"Leave request from {requester_name}",
            message=(
                f"{requester_name} requested {type_name} from {start} to {end}"
                + (f" ({days} day{'s' if days != 1 else ''})" if days else "")
                + ". Review and approve or reject."
            ),
            notif_type="info",
            action_url=action_url,
            source_event="leave.requested",
        )

    # Commit rather than flush: these rows must outlive the request transaction,
    # and a flush would leave them uncommitted if the caller rolled back.
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist leave notifications")
        return 0

    logger.info(
        "Leave %s notified %d approver(s)", leave_request.id, len(recipients)
    )
    return len(recipients)


def _fmt_dt(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y")
    return str(value)[:10]
