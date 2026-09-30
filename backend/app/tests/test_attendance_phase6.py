"""
test_attendance_phase6.py — Phase 6 Attendance + Biometric Experience
Database-backed (real PostgreSQL) verification of the end-to-end workflow.

Coverage (all against the REAL app + REAL Postgres via SessionLocal; only the
non-deterministic ML primitives — face embedding extraction, liveness detection,
emotion analysis — are mocked for determinism, mirroring test_biometrics_integration):

Biometric kiosk lifecycle (/api/v1/attendance/check-in[/check-out]):
  - check-in persists an AttendanceLog (is_live=1, emotion, correct org/user)
  - check-out completes the log (check_out populated)
  - duplicate check-in on the same day is rejected (400)
  - shift-aware late status (check-in past grace -> status "late")
  - biometric security: liveness/spoof -> 403, unknown face -> 404, no image -> 400
  - biometric self-authorization: a face that matches a different user -> 403
  - verify_user_face primitive is secure (unenrolled -> False; match -> True; non-match -> False)

Workforce attendance (/api/v1/workforce/attendance/...):
  - mark creates AttendanceSession + IN/OUT events + AttendanceLog, work_hours computed
  - timeline / events / summary return the real persisted records

Authorization + tenant isolation + data integrity:
  - employee cannot mark attendance for another user (403)
  - cross-tenant timeline / legacy logs access denied (403)
  - persisted records carry the correct org_id / user_id
"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone, date, time as dtime

import pytest
from fastapi.testclient import TestClient

from main import app
from app.db.database import SessionLocal
from app.db.models.all_models import (
    AttendanceLog,
    AttendanceSession,
    AttendanceEvent,
    FaceEmbedding,
    Organization,
    Role,
    RolePermission,
    Permission,
    Department,
    Branch,
    Shift,
    User,
)
from app.core import security
from app.services.face_engine import face_engine
from app.services.liveness import liveness_service

PASSWORD = "Vision@123"
P = "Vision@123"

# 128-d face vectors used as deterministic stand-ins for real embeddings.
EMP_VEC = [round(0.001 * i, 6) for i in range(128)]          # distinct, stable
ADMIN_VEC = [round(0.9 - 0.001 * i, 6) for i in range(128)]   # distinct from EMP_VEC
UNKNOWN_VEC = [0.5] * 128                                    # far from both (> threshold)


def _grant(db, role: Role, *perm_names: str):
    for name in perm_names:
        perm = db.query(Permission).filter(Permission.name == name).first()
        if not perm:
            perm = Permission(name=name, module="attendance", is_active=True)
            db.add(perm)
            db.commit()
        exists = (
            db.query(RolePermission)
            .filter(RolePermission.role_id == role.id, RolePermission.permission_id == perm.id)
            .first()
        )
        if not exists:
            db.add(RolePermission(role_id=role.id, permission_id=perm.id))
    db.commit()


def _get_role(db, name, *perms):
    role = db.query(Role).filter(Role.name == name).first()
    if not role:
        role = Role(name=name)
        db.add(role)
        db.commit()
    if perms:
        _grant(db, role, *perms)
    return role


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def test_setup():
    db = SessionLocal()
    try:
        # Organizations
        org_a = db.query(Organization).filter(Organization.name == "Alpha Corp Phase6").first()
        if not org_a:
            org_a = Organization(
                id=uuid.uuid4(),
                name="Alpha Corp Phase6",
                legal_id=f"ALPHA-P6-{uuid.uuid4().hex[:8]}",
                status="ACTIVE",
            )
            db.add(org_a)

        org_b = db.query(Organization).filter(Organization.name == "Beta Corp Phase6").first()
        if not org_b:
            org_b = Organization(
                id=uuid.uuid4(),
                name="Beta Corp Phase6",
                legal_id=f"BETA-P6-{uuid.uuid4().hex[:8]}",
                status="ACTIVE",
            )
            db.add(org_b)
        db.commit()

        role_emp = _get_role(db, "Employee",
                             "attendance.checkin", "attendance.checkout", "attendance.history")
        role_admin = _get_role(db, "OrgAdmin",
                               "attendance.view", "attendance.checkin", "attendance.checkout",
                               "attendance.history", "attendance.override")

        dept = db.query(Department).filter(Department.name == "Engineering P6").first()
        if not dept:
            dept = Department(org_id=org_a.id, name="Engineering P6", is_deleted=0)
            db.add(dept)
            branch = Branch(org_id=org_a.id, name="HQ P6", code=f"HQ-{uuid.uuid4().hex[:4].upper()}", city="Bangalore")
            db.add(branch)
        db.commit()

        # Shift: 09:00-18:00, grace 5, buffer 15
        shift = db.query(Shift).filter(Shift.shift_name == "P6 Morning", Shift.org_id == org_a.id).first()
        if not shift:
            shift = Shift(
                org_id=org_a.id, shift_name="P6 Morning",
                start_time=dtime(9, 0), end_time=dtime(18, 0),
                grace_period_mins=5, buffer_mins=15,
            )
            db.add(shift)
            db.commit()

        def _user(email_local, role, org):
            u = db.query(User).filter(User.email == f"{email_local}@p6.com").first()
            if not u:
                u = User(
                    org_id=org.id,
                    role_id=role.id,
                    full_name=email_local.replace("_", " ").title(),
                    username=f"{email_local}_{uuid.uuid4().hex[:6]}",
                    email=f"{email_local}@p6.com",
                    employee_id=f"EMP-P6-{uuid.uuid4().hex[:6]}",
                    hashed_password=security.get_password_hash(P),
                    is_active=1,
                    is_deleted=0,
                )
                db.add(u)
            return u

        emp_a = _user("emp_a", role_emp, org_a)
        admin_a = _user("admin_a", role_admin, org_a)
        emp_b = _user("emp_b", role_emp, org_b)
        db.commit()

        emp_a.shift_id = shift.id
        db.commit()

        def _embed(user, vec):
            existing = db.query(FaceEmbedding).filter(FaceEmbedding.user_id == user.id).first()
            if not existing:
                db.add(FaceEmbedding(
                    user_id=user.id, org_id=user.org_id, embedding=vec, is_active=1,
                    encrypted_embedding=b"\x00\x01\x02p6-encrypted-backup",
                    model_name="Facenet", embedding_version="1.0",
                ))
                db.commit()

        _embed(emp_a, EMP_VEC)
        _embed(admin_a, ADMIN_VEC)
        db.commit()

        yield {
            "db": db,
            "org_a": org_a, "org_b": org_b,
            "emp_a": emp_a, "admin_a": admin_a, "emp_b": emp_b,
            "shift": shift,
        }
    finally:
        db.close()


@pytest.fixture(autouse=True)
def clear_attendance(test_setup):
    """Per-test isolation: remove attendance rows (child-first) but keep users/embeddings."""
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()
    app.dependency_overrides.clear()
    db = test_setup["db"]
    org_ids = [test_setup["org_a"].id, test_setup["org_b"].id]
    user_ids = [u.id for u in db.query(User).filter(User.org_id.in_(org_ids)).all()]
    if user_ids:
        db.query(AttendanceEvent).filter(AttendanceEvent.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(AttendanceSession).filter(AttendanceSession.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.query(AttendanceLog).filter(AttendanceLog.user_id.in_(user_ids)).delete(synchronize_session=False)
        db.commit()
    yield
    app.dependency_overrides.clear()


@pytest.fixture(scope="module")
def tokens(client, test_setup):
    from app.core import rate_limit
    rate_limit._fallback_windows.clear()
    app.dependency_overrides.clear()
    def _login(email):
        r = client.post("/api/v1/auth/login", data={"username": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return r.json()["access_token"]
    return {
        "emp_a": _login(test_setup["emp_a"].email),
        "admin_a": _login(test_setup["admin_a"].email),
        "emp_b": _login(test_setup["emp_b"].email),
    }


@pytest.fixture
def ml(monkeypatch):
    """Mock the non-deterministic biometric ML primitives for determinism."""
    monkeypatch.setattr(face_engine, "get_embedding", lambda image_bytes: list(EMP_VEC))
    monkeypatch.setattr(face_engine, "get_emotion", lambda image_bytes: "happy")
    monkeypatch.setattr(liveness_service, "detect_liveness", lambda image_bytes: (True, 0.99))
    return {"liveness": True, "emotion": "happy"}


@pytest.fixture
def ml_spoof(monkeypatch):
    monkeypatch.setattr(face_engine, "get_embedding", lambda image_bytes: list(EMP_VEC))
    monkeypatch.setattr(face_engine, "get_emotion", lambda image_bytes: "neutral")
    monkeypatch.setattr(liveness_service, "detect_liveness", lambda image_bytes: (False, 0.12))
    return {"liveness": False}


def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _img():
    return base64.b64encode(b"fake-face-bytes-for-test").decode("utf-8")


# --------------------------------------------------------------------------- #
#  Biometric kiosk lifecycle (real DB)
# --------------------------------------------------------------------------- #

def test_biometric_checkin_creates_log(client, test_setup, tokens, ml):
    emp = test_setup["emp_a"]
    db = test_setup["db"]
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": _img(), "source": "ai"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_id"] == emp.id
    assert body["source"] == "ai"
    # DB persistence
    log = db.query(AttendanceLog).filter(AttendanceLog.user_id == emp.id).first()
    assert log is not None
    assert log.is_live == 1
    assert log.emotion == "happy"
    assert log.status in ("on_time", "late", "early")
    assert log.source == "ai"
    assert log.check_out is None  # fresh check-in not checked out


def test_biometric_checkin_and_checkout_lifecycle(client, test_setup, tokens, ml):
    db = test_setup["db"]
    emp = test_setup["emp_a"]
    ci = client.post("/api/v1/attendance/check-in",
                     json={"image_base64": _img(), "source": "ai"},
                     headers=_hdr(tokens["emp_a"]))
    assert ci.status_code == 200, ci.text
    co = client.post("/api/v1/attendance/check-out",
                     json={"image_base64": _img(), "source": "ai"},
                     headers=_hdr(tokens["emp_a"]))
    assert co.status_code == 200, co.text
    log = db.query(AttendanceLog).filter(AttendanceLog.user_id == emp.id).first()
    assert log.check_out is not None
    assert co.json()["check_out"] is not None


def test_biometric_duplicate_checkin_blocked(client, test_setup, tokens, ml):
    ci = client.post("/api/v1/attendance/check-in",
                     json={"image_base64": _img(), "source": "ai"},
                     headers=_hdr(tokens["emp_a"]))
    assert ci.status_code == 200
    dup = client.post("/api/v1/attendance/check-in",
                      json={"image_base64": _img(), "source": "ai"},
                      headers=_hdr(tokens["emp_a"]))
    assert dup.status_code == 400
    assert "active" in dup.json()["detail"].lower()


def test_biometric_checkin_late_status(client, test_setup, tokens, ml):
    emp = test_setup["emp_a"]
    db = test_setup["db"]
    # shift start 09:00, grace 5 -> check-in at 10:00 is late
    ts = datetime.now(timezone.utc).replace(hour=10, minute=0, second=0, microsecond=0)
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": _img(), "source": "ai", "timestamp": ts.isoformat()},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "late"
    log = db.query(AttendanceLog).filter(AttendanceLog.user_id == emp.id).first()
    assert log.status == "late"


def test_liveness_spoof_rejected(client, test_setup, tokens, ml_spoof):
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": _img(), "source": "ai"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 403
    detail = r.json().get("detail")
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code == "LIVENESS_FAILED"


def test_biometric_unknown_face_rejected(client, test_setup, tokens, monkeypatch):
    # Embedding that matches nobody in the org
    monkeypatch.setattr(face_engine, "get_embedding", lambda image_bytes: list(UNKNOWN_VEC))
    monkeypatch.setattr(face_engine, "get_emotion", lambda image_bytes: "neutral")
    monkeypatch.setattr(liveness_service, "detect_liveness", lambda image_bytes: (True, 0.99))
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": _img(), "source": "ai"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_biometric_no_image_rejected(client, test_setup, tokens, ml):
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": None, "source": "ai"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 400
    assert "image" in r.json()["detail"].lower()


def test_biometric_crossuser_checkin_forbidden(client, test_setup, tokens, monkeypatch):
    """A face that matches a DIFFERENT user must not let a non-privileged employee
    check in on that user's behalf (biometric identity != session identity)."""
    # Recognize admin_a's embedding while logged in as emp_a (non-privileged)
    monkeypatch.setattr(face_engine, "get_embedding", lambda image_bytes: list(ADMIN_VEC))
    monkeypatch.setattr(face_engine, "get_emotion", lambda image_bytes: "happy")
    monkeypatch.setattr(liveness_service, "detect_liveness", lambda image_bytes: (True, 0.99))
    r = client.post("/api/v1/attendance/check-in",
                    json={"image_base64": _img(), "source": "ai"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 403
    assert "yourself" in r.json()["detail"].lower()


def test_verify_user_face_is_secure(test_setup, monkeypatch):
    """The biometric verification primitive must NOT approve an unenrolled/non-matching face."""
    from app.crud.crud_attendance import attendance
    db = test_setup["db"]
    emp = test_setup["emp_a"]
    admin = test_setup["admin_a"]

    ok, dist = attendance.verify_user_face(db, user_id=emp.id, embedding=list(EMP_VEC))
    assert ok is True and dist == 0.0

    bad, _ = attendance.verify_user_face(db, user_id=admin.id, embedding=list(EMP_VEC))
    assert bad is False

    none_user = test_setup["emp_b"]
    res, _ = attendance.verify_user_face(db, user_id=none_user.id, embedding=list(EMP_VEC))
    assert res is False  # unenrolled user must not verify


# --------------------------------------------------------------------------- #
#  Workforce attendance (real DB)
# --------------------------------------------------------------------------- #

@pytest.fixture
def _patch_workforce(monkeypatch):
    monkeypatch.setattr("app.services.audit_service.audit_service.record", lambda **k: None)
    monkeypatch.setattr("app.services.event_bus.event_bus.publish", lambda *a, **k: None)
    monkeypatch.setattr("app.services.notification_service.notification_service.send", lambda **k: None)
    monkeypatch.setattr(
        "app.services.business_calendar_service.business_calendar_service.is_working_day",
        lambda d, org: True,
    )


def test_workforce_mark_creates_session_events_workhours(client, test_setup, tokens, _patch_workforce):
    db = test_setup["db"]
    emp = test_setup["emp_a"]
    org = test_setup["org_a"]
    now = datetime.now(timezone.utc)
    ci = now.replace(hour=9, minute=0, second=0, microsecond=0)
    co = now.replace(hour=17, minute=0, second=0, microsecond=0)

    r = client.post("/api/v1/workforce/attendance/mark",
                    json={"user_id": emp.id, "channel": "FACE",
                          "work_date": date.today().isoformat(),
                          "check_in": ci.isoformat(), "check_out": co.isoformat()},
                    headers=_hdr(tokens["admin_a"]))
    assert r.status_code == 200, r.text
    sid = r.json()["id"]

    sess = db.query(AttendanceSession).filter(AttendanceSession.id == sid).first()
    assert sess is not None
    assert sess.user_id == emp.id
    assert sess.org_id == org.id
    assert sess.check_in is not None and sess.check_out is not None
    assert sess.work_hours == 8.0  # 09:00 -> 17:00
    assert sess.status == "PRESENT"
    events = db.query(AttendanceEvent).filter(AttendanceEvent.session_id == sid).order_by(AttendanceEvent.event_time).all()
    assert [e.event_type for e in events] == ["IN", "OUT"]
    assert events[0].org_id == org.id


def test_workforce_timeline_events_summary(client, test_setup, tokens, _patch_workforce):
    db = test_setup["db"]
    emp = test_setup["emp_a"]
    now = datetime.now(timezone.utc)
    ci = now.replace(hour=9, minute=0, second=0, microsecond=0)
    co = now.replace(hour=17, minute=0, second=0, microsecond=0)
    client.post("/api/v1/workforce/attendance/mark",
                json={"user_id": emp.id, "channel": "FACE",
                      "work_date": date.today().isoformat(),
                      "check_in": ci.isoformat(), "check_out": co.isoformat()},
                headers=_hdr(tokens["admin_a"]))

    tl = client.get(f"/api/v1/workforce/attendance/timeline/{emp.id}", headers=_hdr(tokens["admin_a"]))
    assert tl.status_code == 200, tl.text
    assert len(tl.json()) >= 1
    sess_id = tl.json()[0]["id"]
    assert tl.json()[0]["status"] == "PRESENT"

    ev = client.get(f"/api/v1/workforce/attendance/events/{sess_id}", headers=_hdr(tokens["admin_a"]))
    assert ev.status_code == 200
    types = [e["event_type"] for e in ev.json()]
    assert "IN" in types and "OUT" in types

    sm = client.get(f"/api/v1/workforce/attendance/summary?user_id={emp.id}", headers=_hdr(tokens["admin_a"]))
    assert sm.status_code == 200
    body = sm.json()
    assert body["present_count"] >= 1
    assert body["total_work_hours"] >= 8.0


# --------------------------------------------------------------------------- #
#  RBAC + tenant isolation + data integrity
# --------------------------------------------------------------------------- #

def test_rbac_employee_cannot_mark_for_others(client, test_setup, tokens, _patch_workforce):
    emp = test_setup["emp_a"]
    admin = test_setup["admin_a"]
    now = datetime.now(timezone.utc)
    r = client.post("/api/v1/workforce/attendance/mark",
                    json={"user_id": admin.id, "channel": "FACE",
                          "work_date": date.today().isoformat(),
                          "check_in": now.replace(hour=9, minute=0).isoformat(),
                          "check_out": now.replace(hour=17, minute=0).isoformat()},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 403


def test_rbac_employee_can_mark_self(client, test_setup, tokens, _patch_workforce):
    emp = test_setup["emp_a"]
    r = client.post("/api/v1/workforce/attendance/mark",
                    json={"user_id": emp.id, "channel": "FACE"},
                    headers=_hdr(tokens["emp_a"]))
    assert r.status_code == 200


def test_rbac_employee_cannot_forge_own_attendance_time(client, test_setup, tokens, _patch_workforce):
    """
    A self-service punch must be timestamped by the server.

    These timestamps feed payable days in payroll, so accepting them from the
    client would let an employee claim a full day's attendance at any hour.
    """
    emp = test_setup["emp_a"]
    now = datetime.now(timezone.utc)
    for field, value in (
        ("work_date", date.today().isoformat()),
        ("check_out", now.replace(hour=17, minute=0).isoformat()),
        ("check_in", now.replace(hour=9, minute=0).isoformat()),
    ):
        r = client.post("/api/v1/workforce/attendance/mark",
                        json={"user_id": emp.id, "channel": "FACE", field: value},
                        headers=_hdr(tokens["emp_a"]))
        assert r.status_code == 400, f"employee forged {field}"
        assert "server" in r.json()["detail"].lower()


def test_tenant_isolation_workforce_timeline(client, test_setup, tokens):
    # emp_b (org B) must NOT read emp_a's (org A) timeline
    r = client.get(f"/api/v1/workforce/attendance/timeline/{test_setup['emp_a'].id}",
                   headers=_hdr(tokens["emp_b"]))
    assert r.status_code == 403


def test_tenant_isolation_workforce_summary(client, test_setup, tokens):
    r = client.get(f"/api/v1/workforce/attendance/summary?user_id={test_setup['emp_a'].id}",
                   headers=_hdr(tokens["emp_b"]))
    # emp_b is not admin and target is another user -> 403
    assert r.status_code == 403


def test_tenant_isolation_legacy_logs(client, test_setup, tokens, ml):
    # Seed a log for emp_a first
    client.post("/api/v1/attendance/check-in",
                json={"image_base64": _img(), "source": "ai"},
                headers=_hdr(tokens["emp_a"]))
    # emp_b (org B) requesting org A's employee's logs -> cross-tenant 403
    r = client.get(f"/api/v1/attendance/logs?user_id={test_setup['emp_a'].id}",
                   headers=_hdr(tokens["emp_b"]))
    assert r.status_code == 403


def test_data_integrity_log_org_user(client, test_setup, tokens, ml):
    db = test_setup["db"]
    emp = test_setup["emp_a"]
    org = test_setup["org_a"]
    client.post("/api/v1/attendance/check-in",
                json={"image_base64": _img(), "source": "ai"},
                headers=_hdr(tokens["emp_a"]))
    log = db.query(AttendanceLog).filter(AttendanceLog.user_id == emp.id).first()
    assert log is not None
    assert log.user_id == emp.id
    # org integrity via join
    u = db.query(User).filter(User.id == log.user_id).first()
    assert u.org_id == org.id
    assert u.org_id != test_setup["org_b"].id
