import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
BASE_URL = "/api/v1"

from app.api import deps
import uuid

class MockRole:
    name = "Admin"

class MockUser:
    id = 1
    org_id = uuid.UUID("12345678-1234-4678-8234-567812345678")
    role_id = 1
    role = MockRole()

def override_get_current_active_user():
    return MockUser()

@pytest.fixture(autouse=True)
def setup_org_overrides():
    app.dependency_overrides[deps.get_current_active_user] = override_get_current_active_user
    yield
    app.dependency_overrides.pop(deps.get_current_active_user, None)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer fake-token"}

def test_create_and_list_api_keys(auth_headers):
    from app.db.database import engine, SessionLocal
    from app.db.models.all_models import Organization, Base
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    org_id = override_get_current_active_user().org_id
    
    # Check if this specific org_id already exists to avoid conflict
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        org = Organization(id=org_id, name="Test Org", legal_id=f"test-legal-{uuid.uuid4()}", primary_color="#4F46E5")
        db.add(org)
        db.commit()
    db.close()

    # 1. Generate API Key
    resp = client.post(
        f"{BASE_URL}/org/api-keys",
        headers=auth_headers,
        json={"scope": "camera_edge", "rate_limit": 100}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "raw_key" in data
    assert data["raw_key"].startswith("vc_")
    assert data["scope"] == "camera_edge"
    assert data["rate_limit"] == 100
    key_id = data["id"]

    # 2. List API Keys
    resp = client.get(f"{BASE_URL}/org/api-keys", headers=auth_headers)
    assert resp.status_code == 200
    keys = resp.json()
    assert len(keys) > 0
    # Find our key
    my_key = next((k for k in keys if k["id"] == key_id), None)
    assert my_key is not None
    assert my_key["is_revoked"] is False

    # 3. Revoke API Key
    resp = client.delete(f"{BASE_URL}/org/api-keys/{key_id}", headers=auth_headers)
    assert resp.status_code == 200
    
    # 4. List again and verify revoked
    resp = client.get(f"{BASE_URL}/org/api-keys", headers=auth_headers)
    keys = resp.json()
    my_key = next((k for k in keys if k["id"] == key_id), None)
    assert my_key["is_revoked"] is True
