import pytest
from pydantic import ValidationError

from app.schema.org import ApiKeyCreate, OrganizationCreate, OrganizationUpdate


def test_organization_create_normalizes_legal_id():
    organization = OrganizationCreate(name=" VisionCore ", legal_id=" in-gst-01 ")

    assert organization.name == "VisionCore"
    assert organization.legal_id == "IN-GST-01"


@pytest.mark.parametrize(
    "payload",
    [
        {"primary_color": "blue"},
        {"primary_color": "#abcd"},
        {"logo_url": "ftp://example.com/logo.png"},
        {"zkp_threshold": 1.1},
    ],
)
def test_organization_update_rejects_invalid_branding(payload):
    with pytest.raises(ValidationError):
        OrganizationUpdate(**payload)


@pytest.mark.parametrize("rate_limit", [0, 10_001])
def test_api_key_rate_limit_is_bounded(rate_limit):
    with pytest.raises(ValidationError):
        ApiKeyCreate(rate_limit=rate_limit)
