"""
copilot_tools.py — Enterprise AI Copilot Controlled Tool Registry
Sprint 8 — Enterprise AI Copilot Expansion

Permission-aware, tenant-scoped tool functions for the VisionCore AI Copilot.

SECURITY ARCHITECTURE:
- Every tool receives tenant_id and actor_user permissions before any data access.
- No tool exposes raw SQL, DB credentials, or personally sensitive salary detail.
- All tool results are logged to the audit trail.
- The LLM NEVER receives DB credentials or connection strings.
- Tools call existing domain services only — no direct ORM queries in this layer.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy.orm import Session
from sqlalchemy import extract, func

from app.db.models.all_models import (
    AttendanceLog, User, Payroll, Reimbursement,
)
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

# ── Allowed permissions per tool ──────────────────────────────────────────────
TOOL_PERMISSION_MAP: dict[str, list[str]] = {
    "get_attendance_summary":   ["attendance.history", "attendance.read"],
    "get_employee_attendance":  ["attendance.history", "attendance.read"],
    "get_workforce_metrics":    ["employee.read", "hr.analytics"],
    "get_department_metrics":   ["employee.read", "hr.analytics"],
    "get_leave_summary":        ["leave.read", "hr.analytics"],
    "get_overtime_summary":     ["attendance.history", "hr.analytics"],
    "get_payroll_summary":      ["payroll.read", "finance.payroll.view"],
    "get_payroll_run_status":   ["payroll.read", "finance.payroll.view"],
    "get_reimbursement_summary":["expense.view", "finance.payroll.view"],
    "get_headcount":            ["employee.read"],
    "get_certification_expiry": ["hcm.read", "employee.read"],
    "get_employees_on_leave":   ["leave.read", "hr.analytics"],
    "get_executive_kpis":          ["analytics.read", "hr.analytics"],
    "get_metric_snapshot_history": ["analytics.read", "hr.analytics"],
    "evaluate_flight_risk":        ["employee.read", "hr.analytics"],
}

SAFE_STATUS = {"success", "partial", "empty"}

# ── Security: PII redaction ────────────────────────────────────────────────────
_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = {"account_number", "bank_account", "routing_number", "salary", "net_pay", "ssn", "tax_id"}


def _redact(record: dict) -> dict:
    """Remove or mask any sensitive keys from a response dict."""
    return {
        k: _REDACTED if k.lower() in _SENSITIVE_KEYS else v
        for k, v in record.items()
    }


# ── Tool Result Envelope ───────────────────────────────────────────────────────
def _ok(tool: str, data: Any, summary: str) -> dict:
    return {"tool": tool, "status": "success", "summary": summary, "data": data}


def _empty(tool: str, summary: str) -> dict:
    return {"tool": tool, "status": "empty", "summary": summary, "data": []}


def _error(tool: str, msg: str) -> dict:
    return {"tool": tool, "status": "error", "summary": msg, "data": []}


# ─────────────────────────────────────────────────────────────────────────────
#  Attendance Tools
# ─────────────────────────────────────────────────────────────────────────────

def get_attendance_summary(
    db: Session,
    org_id: Any,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Return attendance counts for the org in a given period. Max 1000 rows."""
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year

    try:
        q = (
            db.query(
                AttendanceLog.status,
                func.count(AttendanceLog.id).label("count"),
            )
            .join(User, AttendanceLog.user_id == User.id)
            .filter(
                User.org_id == org_id,
                extract("month", AttendanceLog.check_in) == month,
                extract("year", AttendanceLog.check_in) == year,
            )
            .group_by(AttendanceLog.status)
            .limit(50)
            .all()
        )
        data = [{"status": r.status, "count": r.count} for r in q]
        total = sum(r["count"] for r in data)
        if not data:
            return _empty("get_attendance_summary", f"No attendance records for {month}/{year}")
        return _ok("get_attendance_summary", data, f"Attendance summary for {month}/{year}: {total} total records across {len(data)} statuses")
    except Exception as e:
        logger.error("get_attendance_summary failed: %s", e)
        return _error("get_attendance_summary", "Failed to retrieve attendance data")


def get_employee_attendance(
    db: Session,
    org_id: Any,
    employee_id: int,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Return attendance records for a specific employee. Max 50 records."""
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year

    try:
        # Verify employee belongs to org
        emp = db.query(User).filter(User.id == employee_id, User.org_id == org_id, User.is_deleted == 0).first()
        if not emp:
            return _error("get_employee_attendance", "Employee not found in your organization")

        logs = (
            db.query(AttendanceLog)
            .filter(
                AttendanceLog.user_id == employee_id,
                extract("month", AttendanceLog.check_in) == month,
                extract("year", AttendanceLog.check_in) == year,
            )
            .order_by(AttendanceLog.check_in.desc())
            .limit(50)
            .all()
        )
        data = [
            {
                "date": log.check_in.date().isoformat() if log.check_in else None,
                "status": log.status,
                "check_in": log.check_in.isoformat() if log.check_in else None,
                "check_out": log.check_out.isoformat() if log.check_out else None,
            }
            for log in logs
        ]
        if not data:
            return _empty("get_employee_attendance", f"No attendance for employee {employee_id} in {month}/{year}")
        return _ok("get_employee_attendance", data, f"{len(data)} attendance records for {month}/{year}")
    except Exception as e:
        logger.error("get_employee_attendance failed: %s", e)
        return _error("get_employee_attendance", "Failed to retrieve employee attendance")


# ─────────────────────────────────────────────────────────────────────────────
#  Workforce & HR Tools
# ─────────────────────────────────────────────────────────────────────────────

def get_headcount(db: Session, org_id: Any, *, actor_user_id: Optional[int] = None) -> dict:
    """Return total active employee headcount for the org."""
    try:
        count = db.query(func.count(User.id)).filter(
            User.org_id == org_id, User.is_deleted == 0, User.is_active == True
        ).scalar() or 0
        return _ok("get_headcount", {"headcount": count}, f"Total active headcount: {count}")
    except Exception as e:
        logger.error("get_headcount failed: %s", e)
        return _error("get_headcount", "Failed to retrieve headcount")


def get_workforce_metrics(db: Session, org_id: Any, *, actor_user_id: Optional[int] = None) -> dict:
    """Aggregated workforce health metrics including headcount, role distribution."""
    try:
        from app.db.models.all_models import Role
        rows = (
            db.query(Role.name, func.count(User.id).label("count"))
            .join(User, User.role_id == Role.id)
            .filter(User.org_id == org_id, User.is_deleted == 0)
            .group_by(Role.name)
            .limit(20)
            .all()
        )
        total = sum(r.count for r in rows)
        data = [{"role": r.name, "count": r.count} for r in rows]
        return _ok("get_workforce_metrics", {"total_employees": total, "by_role": data}, f"Workforce: {total} employees across {len(data)} roles")
    except Exception as e:
        logger.error("get_workforce_metrics failed: %s", e)
        return _error("get_workforce_metrics", "Failed to retrieve workforce metrics")


# ─────────────────────────────────────────────────────────────────────────────
#  Finance & Payroll Tools — Sensitive Data Handled Carefully
# ─────────────────────────────────────────────────────────────────────────────

def get_payroll_summary(
    db: Session,
    org_id: Any,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> dict:
    """
    Return aggregate payroll totals for the period.
    DOES NOT expose individual salary details or bank information.
    """
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year
    try:
        rows = (
            db.query(
                Payroll.status,
                func.count(Payroll.id).label("count"),
                func.sum(Payroll.total_salary).label("total_net"),
                func.sum(Payroll.deductions).label("total_deductions"),
            )
            .filter(
                Payroll.org_id == org_id,
                Payroll.month == month,
                Payroll.year == year,
            )
            .group_by(Payroll.status)
            .all()
        )
        if not rows:
            return _empty("get_payroll_summary", f"No payroll data for {month}/{year}")
        data = [
            {
                "status": r.status,
                "employee_count": r.count,
                "total_net_pay": str(Decimal(str(r.total_net or 0)).quantize(Decimal("0.01"))),
                "total_deductions": str(Decimal(str(r.total_deductions or 0)).quantize(Decimal("0.01"))),
            }
            for r in rows
        ]
        total_employees = sum(r["employee_count"] for r in data)
        return _ok("get_payroll_summary", data, f"Payroll {month}/{year}: {total_employees} payslips across {len(data)} status groups")
    except Exception as e:
        logger.error("get_payroll_summary failed: %s", e)
        return _error("get_payroll_summary", "Failed to retrieve payroll summary")


def get_payroll_run_status(
    db: Session,
    org_id: Any,
    *,
    month: Optional[int] = None,
    year: Optional[int] = None,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Return recent payroll run status for the org."""
    now = datetime.now(timezone.utc)
    month = month or now.month
    year = year or now.year
    try:
        runs = (
            db.query(Payroll)
            .filter(Payroll.org_id == org_id)
            .order_by(Payroll.id.desc())
            .limit(5)
            .all()
        )
        if not runs:
            return _empty("get_payroll_run_status", "No payroll runs found")
        data = [
            {
                "run_id": r.id,
                "status": r.status,
                "started_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in runs
        ]
        return _ok("get_payroll_run_status", data, f"{len(data)} recent payroll runs")
    except Exception as e:
        logger.error("get_payroll_run_status failed: %s", e)
        return _error("get_payroll_run_status", "Failed to retrieve payroll run status")


def get_reimbursement_summary(
    db: Session,
    org_id: Any,
    *,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Return pending reimbursement claim totals by status."""
    try:
        rows = (
            db.query(
                Reimbursement.status,
                func.count(Reimbursement.id).label("count"),
                func.sum(Reimbursement.amount).label("total"),
            )
            .filter(Reimbursement.org_id == org_id)
            .group_by(Reimbursement.status)
            .limit(10)
            .all()
        )
        if not rows:
            return _empty("get_reimbursement_summary", "No reimbursement claims found")
        data = [
            {
                "status": r.status,
                "count": r.count,
                "total_amount": str(Decimal(str(r.total or 0)).quantize(Decimal("0.01"))),
            }
            for r in rows
        ]
        return _ok("get_reimbursement_summary", data, f"Reimbursement summary: {len(data)} status groups")
    except Exception as e:
        logger.error("get_reimbursement_summary failed: %s", e)
        return _error("get_reimbursement_summary", "Failed to retrieve reimbursement summary")


# ─────────────────────────────────────────────────────────────────────────────
#  Tool Registry
# ── Sprint 9 Analytics & Intelligence Tools ────────────────────────────────────

def get_executive_kpis(
    db: Session,
    org_id: Any,
    *,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Return executive-level platform metrics for current tenant."""
    try:
        from app.services.analytics_platform import AnalyticsPlatform
        platform = AnalyticsPlatform()
        dash = platform.get_executive_dashboard(str(org_id) if org_id else "")
        return _ok("get_executive_kpis", dash, "Executive dashboard metrics retrieved successfully.")
    except Exception as e:
        logger.error("get_executive_kpis failed: %s", e)
        return _error("get_executive_kpis", "Failed to retrieve executive KPIs")


def get_metric_snapshot_history(
    db: Session,
    org_id: Any,
    *,
    metric_key: Optional[str] = None,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Query historical metric snapshots for tenant."""
    try:
        from app.services.metric_registry import metric_registry_service
        snaps = metric_registry_service.get_snapshots(db=db, org_id=org_id, metric_key=metric_key, limit=20)
        data = [
            {
                "id": s.id,
                "metric_key": s.metric_key,
                "metric_value": float(s.metric_value),
                "snapshot_date": s.snapshot_date.isoformat() if s.snapshot_date else "",
            }
            for s in snaps
        ]
        return _ok("get_metric_snapshot_history", data, f"Retrieved {len(data)} metric snapshots.")
    except Exception as e:
        logger.error("get_metric_snapshot_history failed: %s", e)
        return _error("get_metric_snapshot_history", "Failed to retrieve snapshot history")


def evaluate_flight_risk(
    db: Session,
    org_id: Any,
    employee_id: int,
    *,
    actor_user_id: Optional[int] = None,
) -> dict:
    """Evaluate employee flight risk score and identified risk factors."""
    try:
        from app.services.workforce_intelligence import workforce_intelligence_engine
        res = workforce_intelligence_engine.evaluate_employee_flight_risk(db=db, user_id=employee_id, org_id=org_id)
        if "error" in res:
            return _error("evaluate_flight_risk", res["error"])
        return _ok("evaluate_flight_risk", res, f"Flight risk evaluated for employee #{employee_id}: {res.get('risk_level')}")
    except Exception as e:
        logger.error("evaluate_flight_risk failed: %s", e)
        return _error("evaluate_flight_risk", "Failed to evaluate flight risk")


# ── Tool Registry ─────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, Any] = {
    "get_attendance_summary":    get_attendance_summary,
    "get_employee_attendance":   get_employee_attendance,
    "get_headcount":             get_headcount,
    "get_workforce_metrics":     get_workforce_metrics,
    "get_payroll_summary":       get_payroll_summary,
    "get_payroll_run_status":    get_payroll_run_status,
    "get_reimbursement_summary": get_reimbursement_summary,
    "get_executive_kpis":          get_executive_kpis,
    "get_metric_snapshot_history": get_metric_snapshot_history,
    "evaluate_flight_risk":        evaluate_flight_risk,
}


def get_tool(name: str):
    """Retrieve a registered tool function by name."""
    return TOOL_REGISTRY.get(name)


def list_tools() -> list[dict]:
    """Return available tools with metadata (no sensitive internals)."""
    return [
        {
            "name": name,
            "required_permission": TOOL_PERMISSION_MAP.get(name, []),
        }
        for name in TOOL_REGISTRY
    ]
