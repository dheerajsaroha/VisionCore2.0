import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI
import importlib, sys

# Import health_router module in isolation to avoid the __init__ import chain
# (which transitively loads payroll_engine → LoanRepayment, a pre-existing issue)
import importlib.util, os
_spec = importlib.util.spec_from_file_location(
    "health_router_mod",
    os.path.join(os.path.dirname(__file__), "../routers/health_router.py"),
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
health_router = _mod.router


# ── Minimal test app ──────────────────────────────────────────────────────────

app = FastAPI()
app.include_router(health_router)


@pytest.fixture
def client():
    return TestClient(app)


# ── WorkforceIntelligenceEngine Tests ─────────────────────────────────────────

class TestWorkforceIntelligence:
    def test_evaluate_employee_flight_risk_not_found(self):
        """evaluate_employee_flight_risk should return error dict for unknown user."""
        from app.services.workforce_intelligence import WorkforceIntelligenceEngine
        from uuid import uuid4
        engine = WorkforceIntelligenceEngine()
        mock_db = MagicMock()
        mock_db.execute.return_value.scalar_one_or_none.return_value = None
        result = engine.evaluate_employee_flight_risk(mock_db, user_id=999, org_id=uuid4())
        assert "error" in result

    def test_evaluate_employee_flight_risk_low_risk(self):
        """evaluate_employee_flight_risk returns LOW risk for normal user."""
        from app.services.workforce_intelligence import WorkforceIntelligenceEngine
        from uuid import uuid4
        from datetime import datetime, timezone, timedelta
        engine = WorkforceIntelligenceEngine()
        mock_db = MagicMock()
        mock_user = MagicMock()
        mock_user.created_at = datetime.now(timezone.utc) - timedelta(days=500)
        mock_db.execute.return_value.scalar_one_or_none.return_value = mock_user
        mock_db.scalars.return_value.all.return_value = []  # no leaves, no reviews
        result = engine.evaluate_employee_flight_risk(mock_db, user_id=1, org_id=uuid4())
        assert "flight_risk_score" in result
        assert result["risk_level"] == "LOW"

    def test_evaluate_organization_capacity(self):
        """evaluate_organization_capacity returns proper dict structure."""
        from app.services.workforce_intelligence import WorkforceIntelligenceEngine
        from uuid import uuid4
        engine = WorkforceIntelligenceEngine()
        mock_db = MagicMock()
        mock_db.scalars.return_value.all.return_value = [MagicMock()] * 50
        result = engine.evaluate_organization_capacity(mock_db, uuid4())
        assert "active_headcount" in result
        assert result["active_headcount"] == 50
        assert "attrition_propensity_index" in result


# ── Health Router Unit Tests ──────────────────────────────────────────────────

class TestHealthRouterUnit:
    def test_liveness_is_200(self):
        """GET /health/liveness must return 200 with ALIVE status."""
        from fastapi.testclient import TestClient
        # Override dependency
        from app.api import deps
        def override_get_db():
            mock_db = MagicMock()
            mock_db.execute.return_value = MagicMock()
            yield mock_db

        app2 = FastAPI()
        app2.include_router(health_router)
        app2.dependency_overrides[deps.get_db] = override_get_db
        client2 = TestClient(app2)
        response = client2.get("/health/liveness")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ALIVE"

    def test_readiness_ok_with_db(self):
        """GET /health/readiness must return 200 when DB connection succeeds."""
        from fastapi.testclient import TestClient
        from app.api import deps
        mock_db = MagicMock()

        def override_get_db():
            yield mock_db

        app3 = FastAPI()
        app3.include_router(health_router)
        app3.dependency_overrides[deps.get_db] = override_get_db
        client3 = TestClient(app3)
        response = client3.get("/health/readiness")
        assert response.status_code == 200
        assert response.json()["status"] == "READY"

    def test_readiness_503_when_db_fails(self):
        """GET /health/readiness must return 503 when DB connection fails."""
        from fastapi.testclient import TestClient
        from app.api import deps

        def override_get_db_broken():
            db = MagicMock()
            db.execute.side_effect = Exception("DB connection failed")
            yield db

        app4 = FastAPI()
        app4.include_router(health_router)
        app4.dependency_overrides[deps.get_db] = override_get_db_broken
        client4 = TestClient(app4)
        response = client4.get("/health/readiness")
        assert response.status_code == 503


# ── Copilot Sprint 9 Tool Tests ───────────────────────────────────────────────

class TestCopilotSprint9Tools:
    def test_get_executive_kpis_error_handled(self):
        """get_executive_kpis should return error dict on exception."""
        from app.services.ai.copilot_tools import get_executive_kpis
        mock_db = MagicMock()
        with patch("app.services.analytics_platform.AnalyticsPlatform", side_effect=Exception("fail")):
            result = get_executive_kpis(mock_db, "org-123")
        assert result["status"] == "error"

    def test_get_metric_snapshot_history_empty(self):
        """get_metric_snapshot_history returns empty list when no snapshots."""
        from app.services.ai.copilot_tools import get_metric_snapshot_history
        mock_db = MagicMock()
        with patch("app.services.metric_registry.metric_registry_service.get_snapshots", return_value=[]):
            result = get_metric_snapshot_history(mock_db, "org-123", metric_key="workforce_headcount")
        assert result["status"] == "success"
        assert result["data"] == []

    def test_evaluate_flight_risk_tool_user_not_found(self):
        """evaluate_flight_risk should return error dict when user not found."""
        from app.services.ai.copilot_tools import evaluate_flight_risk
        mock_db = MagicMock()
        with patch("app.services.workforce_intelligence.workforce_intelligence_engine.evaluate_employee_flight_risk", return_value={"error": "User not found"}):
            result = evaluate_flight_risk(mock_db, "org-123", employee_id=999)
        assert result["status"] == "error"
