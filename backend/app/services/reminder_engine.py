"""
reminder_engine.py — Policy Acknowledgement Reminder & Escalation Engine
Sprint 4 — Entity 5
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_

from app.db.models.all_models import (
    PolicyDocument, PolicyDistribution, PolicyAcknowledgement,
    PolicyReminder, PolicyNotification, User
)
from app.crud.crud_policy import (
    crud_policy_document, crud_policy_reminder, crud_policy_acknowledgement,
    crud_policy_notification
)


class ReminderEngine:
    """Automated reminder scheduling, sending, and escalation."""

    @staticmethod
    def process_pending_reminders(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Process all active reminders — send notifications for unacknowledged policies."""
        now = datetime.now(timezone.utc)
        sent_count = 0
        escalated_count = 0
        errors = []

        reminders = db.query(PolicyReminder).filter(
            PolicyReminder.organization_id == org_id,
            PolicyReminder.is_active.is_(True)
        ).all()

        for reminder in reminders:
            try:
                # Find users who haven't acknowledged this policy
                doc = crud_policy_document.get_by_id(db, reminder.document_id)
                if not doc or doc.status not in ["published", "effective"]:
                    continue

                # Get all users this policy is distributed to
                distributions = db.query(PolicyDistribution).filter(
                    PolicyDistribution.document_id == reminder.document_id,
                    PolicyDistribution.is_active.is_(True)
                ).all()

                target_user_ids = set()
                for dist in distributions:
                    if dist.distribution_type == "organization":
                        users = db.query(User.id).filter(
                            User.org_id == org_id,
                            User.is_deleted == 0
                        ).all()
                        target_user_ids.update(u.id for u in users)
                    elif dist.distribution_type == "department" and dist.target_dept_id:
                        users = db.query(User.id).filter(
                            User.dept_id == dist.target_dept_id,
                            User.is_deleted == 0
                        ).all()
                        target_user_ids.update(u.id for u in users)
                    elif dist.distribution_type == "user" and dist.target_user_id:
                        target_user_ids.add(dist.target_user_id)

                for uid in target_user_ids:
                    ack = crud_policy_acknowledgement.get_for_user(db, reminder.document_id, uid)
                    is_acked = ack is not None and ack.is_acknowledged

                    if not is_acked:
                        # Check how many reminders already sent
                        existing_notifs = db.query(PolicyNotification).filter(
                            PolicyNotification.document_id == reminder.document_id,
                            PolicyNotification.user_id == uid,
                            PolicyNotification.notification_type == "policy_reminder"
                        ).count()

                        if existing_notifs < reminder.max_reminders:
                            # Send reminder
                            notif = PolicyNotification(
                                organization_id=org_id,
                                document_id=reminder.document_id,
                                user_id=uid,
                                notification_type="policy_reminder",
                                title=f"Reminder: Please acknowledge '{doc.title}'",
                                message=f"Policy '{doc.title}' requires your acknowledgement. "
                                        f"This is reminder {existing_notifs + 1} of {reminder.max_reminders}."
                            )
                            db.add(notif)
                            sent_count += 1

                            # Update acknowledgement reminder count
                            if ack:
                                ack.reminder_count = existing_notifs + 1
                                db.add(ack)
                        else:
                            # Escalate
                            if reminder.escalation_user_id:
                                esc_notif = PolicyNotification(
                                    organization_id=org_id,
                                    document_id=reminder.document_id,
                                    user_id=reminder.escalation_user_id,
                                    notification_type="policy_escalation",
                                    title=f"ESCALATION: Policy '{doc.title}' unacknowledged by user",
                                    message=f"User ID {uid} has not acknowledged '{doc.title}' "
                                            f"after {reminder.max_reminders} reminders."
                                )
                                db.add(esc_notif)
                                escalated_count += 1

            except Exception as e:
                errors.append(f"Reminder {reminder.id}: {str(e)}")

        db.commit()

        return {
            "reminders_processed": len(reminders),
            "reminders_sent": sent_count,
            "escalations_sent": escalated_count,
            "errors": errors
        }

    @staticmethod
    def get_reminder_stats(db: Session, org_id: UUID) -> Dict[str, Any]:
        """Get reminder system statistics."""
        active_reminders = db.query(PolicyReminder).filter(
            PolicyReminder.organization_id == org_id,
            PolicyReminder.is_active.is_(True)
        ).count()

        unread_notifs = db.query(PolicyNotification).filter(
            PolicyNotification.organization_id == org_id,
            PolicyNotification.is_read == False
        ).count()

        unacknowledged = db.query(PolicyAcknowledgement).join(
            PolicyDocument, PolicyAcknowledgement.document_id == PolicyDocument.id
        ).filter(
            PolicyDocument.organization_id == org_id,
            PolicyAcknowledgement.is_acknowledged == False
        ).count()

        return {
            "active_reminders": active_reminders,
            "unread_notifications": unread_notifs,
            "unacknowledged_policies": unacknowledged
        }


reminder_engine = ReminderEngine()

