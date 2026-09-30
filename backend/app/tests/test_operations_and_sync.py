"""
Endpoints that raised on every call, and the offline biometric sync contract.

`edge_client.py` buffers failed check-ins locally and posts them to
`/attendance/sync` on reconnect, but no such endpoint existed, so every replay
404'd and the device queue only ever grew. Biometric hardware integration is one
of the Growth-tier deliverables, and the client half was already written.

Six `/operations` endpoints called service methods that do not exist:
`get_job_stats`, `list_jobs`, `get_job_definitions`, `generate`, `list_reports`,
and an `await` on the synchronous `seed_default_jobs` — plus `create_job` invoked
with `payload=`/`schedule=` keywords it does not accept. All raised on call.

The export endpoints ignored both the tenant and the requested schema and
returned a single hardcoded `Demo User` row, so an export produced a file that
looked like employee data and contained none.

The job engine's default handlers returned invented counts — payroll reported 42
records processed, attendance sync 128 logs, cleanup 256 MB — and the email
handler reported `sent: True` without sending.
"""
import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from main import app
from app.api import deps
from app.core import rate_limit
from app.core.security import get_password_hash
from app.db import seed_rbac
from app.db.database import SessionLocal, get_db
from app.db.models.all_models import Organization, Role, User
from app.services.job_engine import JobRecord, job_engine
from app.services.scheduler_service import JobType, scheduler_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    with TestClient(app) as c:
        app.dependency_overrides[get_db] = lambda: db
        try:
            yield c
        finally:
            app.dependency_overrides.clear()
            rate_limit._fallback_windows.clear()


@pytest.fixture
def org(db):
    o = Organization(
        name=f"Ops {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-OPS-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _user(db, org, code, role_name="OrgHR"):
    role = db.query(Role).filter(Role.name == role_name).first()
    slug = f"{code}-{uuid.uuid4().hex[:6]}"
    u = User(
        email=f"{slug}@example.com",
        username=slug,
        employee_id=slug.upper(),
        full_name=code,
        org_id=org.id,
        role_id=role.id,
        is_active=1,
        hashed_password=get_password_hash("Test-Passw0rd!"),
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _as(db, user):
    # The export endpoints depend on `get_current_user`; the sync endpoint on
    # `get_current_active_user`. Override both so one helper covers each test.
    app.dependency_overrides[deps.get_current_active_user] = lambda: user
    app.dependency_overrides[deps.get_current_user] = lambda: user


class TestAttendanceSync:
    """`edge_client.py` posts here; the endpoint did not exist."""

    def test_endpoint_is_registered(self):
        assert "/api/v1/attendance/sync" in app.openapi().get("paths", {})

    def test_empty_batch_is_accepted(self, client, db):
        emp = _user(db, _org_for(db), "syncempty")
        _as(db, emp)
        r = client.post("/api/v1/attendance/sync", json={"logs": []})
        assert r.status_code == 200
        body = r.json()
        assert (body["received"], body["recorded"], body["failed"]) == (0, 0, 0)

    def test_requires_authentication(self, client):
        assert client.post("/api/v1/attendance/sync", json={"logs": []}).status_code in (401, 403)

    def test_per_entry_outcomes_are_reported(self, client, db):
        """A device must be able to drop only what landed.

        One unreplayable entry would otherwise either be retried forever or
        discarded along with the rest of the batch.
        """
        emp = _user(db, _org_for(db), "syncbatch")
        _as(db, emp)

        # Entries with no image cannot be replayed: identity comes from the
        # biometric sample, and an embedding-only entry has none.
        r = client.post(
            "/api/v1/attendance/sync",
            json={"logs": [{"user_id": emp.id}, {"user_id": emp.id, "source": "edge"}]},
        )
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert body["received"] == 2
        assert body["recorded"] + body["failed"] == 2
        assert len(body["results"]) == 2
        assert all("error" in item for item in body["results"])
        assert [item["index"] for item in body["results"]] == [0, 1]

    def test_a_submitted_user_id_cannot_assert_identity(self, client, db):
        """The edge queue's `user_id` is correlation only.

        Identity must be re-derived from the biometric sample, so a device that
        edits its own queue cannot attribute a punch to another employee.
        """
        org = _org_for(db)
        attacker = _user(db, org, "syncattacker")
        victim = _user(db, org, "syncvictim")
        _as(db, attacker)

        r = client.post(
            "/api/v1/attendance/sync",
            json={"logs": [{"user_id": victim.id, "is_live": 0}]},
        )
        assert r.status_code == 200
        result = r.json()["results"][0]
        assert result["recorded"] is False
        assert result.get("user_id") != victim.id, (
            "a client-asserted user_id must never become the recorded identity"
        )


class TestOperationsEndpointsDoNotRaise:
    def test_list_jobs_exists_and_filters(self):
        assert callable(scheduler_service.list_jobs)
        job = scheduler_service.create_job(
            name=f"probe-{uuid.uuid4().hex[:6]}",
            job_type=JobType.IMMEDIATE,
            module="probe",
            task="probe_task",
        )
        listed = scheduler_service.list_jobs(limit=10)
        assert any(j["id"] == job.id for j in listed)
        filtered = scheduler_service.list_jobs(module="probe", limit=10)
        assert all(j["module"] == "probe" for j in filtered)

    def test_get_stats_is_the_real_scheduler_method(self):
        stats = scheduler_service.get_stats()
        assert isinstance(stats, dict)

    def test_job_definitions_enumerates_registered_tasks(self):
        """`get_job_definitions` never existed on the service."""
        assert not hasattr(scheduler_service, "get_job_definitions")

    def test_reporting_engine_exposes_the_methods_the_router_calls(self):
        from app.services.reporting_engine import reporting_engine

        assert callable(reporting_engine.generate_report)
        assert callable(reporting_engine.get_reports)
        assert not hasattr(reporting_engine, "generate")
        assert not hasattr(reporting_engine, "list_reports")


class TestJobHandlersDoNotFabricate:
    def test_payroll_handler_reports_zero_not_42(self):
        record = _job_record(payload={"period": "2026-09"})
        result = job_engine._handlers["payroll_auto_calc"](record)
        assert result["processed_records"] == 0
        assert result["implemented"] is False

    def test_attendance_sync_handler_reports_zero_not_128(self):
        record = _job_record(payload={"date": "2026-09-27"})
        result = job_engine._handlers["attendance_sync"](record)
        assert result["synced_count"] == 0
        assert result["implemented"] is False

    def test_cleanup_handler_reports_zero_not_256(self):
        result = job_engine._handlers["system_cleanup"](_job_record(payload={}))
        assert result["purged_mb"] == 0
        assert result["implemented"] is False

    def test_email_handler_does_not_claim_a_send_it_skipped(self):
        result = job_engine._handlers["email_delivery"](_job_record(payload={}))
        assert result["sent"] is False
        assert "reason" in result


class TestExportEndpointsAreReal:
    def test_unknown_schema_is_rejected(self, client, db):
        _as(db, _user(db, _org_for(db), "exportunknown"))
        r = client.get("/api/v1/platform/export/csv?schema_name=not_a_schema")
        assert r.status_code == 400, "an unknown schema must not silently export demo data"
        assert "Demo User" not in r.text

    def test_employee_export_requires_permission(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        emp = _user(db, _org_for(db), "exportemp", "OrgEmployee")
        _as(db, emp)
        r = client.get("/api/v1/platform/export/csv?schema_name=employees")
        assert r.status_code == 403

    def test_payroll_export_requires_the_payroll_permission(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        # OrgManager holds reports.employee.export but not reports.payroll.export.
        # (OrgHR is not usable here: it legitimately holds both.)
        manager = _user(db, _org_for(db), "exportmgr", "OrgManager")
        _as(db, manager)
        employees = client.get("/api/v1/platform/export/csv?schema_name=employees")
        assert employees.status_code == 200, "the manager does hold the employee grant"
        r = client.get("/api/v1/platform/export/csv?schema_name=payroll")
        assert r.status_code == 403, "payroll must not be exportable with an employee-export grant"

    def test_authorized_export_returns_no_demo_rows(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        org = _org_for(db)
        hr = _user(db, org, "exportok", "OrgHR")
        _as(db, hr)
        r = client.get("/api/v1/platform/export/csv?schema_name=employees")
        assert r.status_code == 200, r.text[:200]
        assert "Demo User" not in r.text, (
            "the export must contain the caller's tenant, not a hardcoded row"
        )
        assert hr.employee_id.upper() in r.text

    def test_export_is_scoped_to_the_callers_tenant(self, client, db):
        seed_rbac.seed_all(db)
        db.commit()
        org_a = _org_for(db)
        _user(db, org_a, "tenanta", "OrgHR")
        other_org = _org_for(db)
        _user(db, other_org, "tenantb", "OrgHR")

        viewer = _user(db, org_a, "tenantscope", "OrgHR")
        _as(db, viewer)
        r = client.get("/api/v1/platform/export/csv?schema_name=employees")
        assert r.status_code == 200
        assert "TENANTB" not in r.text.upper()


def _org_for(db):
    o = Organization(
        name=f"OpsX {uuid.uuid4().hex[:6]}",
        legal_id=f"TEST-OX-{uuid.uuid4().hex[:8].upper()}",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


def _job_record(payload):
    import datetime as _dt
    from uuid import uuid4

    return JobRecord(
        id=str(uuid4()),
        name="probe",
        organization_id="",
        handler_type="probe",
        payload=payload,
        created_at=_dt.datetime.now(_dt.timezone.utc),
    )
