"""
integration.py — Integration Schemas for Cloud Integration Framework
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Defines Pydantic models for:
- Webhook configurations
- OAuth2 client configurations
- API Key management
- External system connectors
- Integration health/status
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# =============================================================================
#  Enums
# =============================================================================

class IntegrationType(str, Enum):
    WEBHOOK_INBOUND = "webhook_inbound"
    WEBHOOK_OUTBOUND = "webhook_outbound"
    OAUTH2_CLIENT = "oauth2_client"
    API_KEY = "api_key"
    CONNECTOR = "connector"
    CUSTOM = "custom"


class ConnectorType(str, Enum):
    SLACK = "slack"
    EMAIL_SMTP = "email_smtp"
    SMS_TWILIO = "sms_twilio"
    CALENDAR = "calendar"
    STORAGE_S3 = "storage_s3"
    CRM_SALESFORCE = "crm_salesforce"
    HRIS = "hris"
    PAYMENT_STRIPE = "payment_stripe"
    CUSTOM = "custom"


class WebhookMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class IntegrationStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"
    PENDING = "pending"
    DISCONNECTED = "disconnected"


class WebhookEvent(str, Enum):
    # Authentication
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    # Organization
    ORG_CREATED = "org.created"
    ORG_UPDATED = "org.updated"
    # EAAC
    PERMISSION_GRANTED = "permission.granted"
    PERMISSION_REVOKED = "permission.revoked"
    ROLE_ASSIGNED = "role.assigned"
    SUBSCRIPTION_CHANGED = "subscription.changed"
    # HR
    LEAVE_REQUESTED = "leave.requested"
    LEAVE_APPROVED = "leave.approved"
    ATTENDANCE_CHECKIN = "attendance.checkin"
    PAYROLL_GENERATED = "payroll.generated"
    CANDIDATE_HIRED = "candidate.hired"
    # Performance
    REVIEW_SUBMITTED = "review.submitted"
    PROMOTION_APPROVED = "promotion.approved"
    # Policy
    POLICY_PUBLISHED = "policy.published"
    COMPLIANCE_BREACH = "compliance.breach"
    # Asset
    ASSET_ASSIGNED = "asset.assigned"
    ASSET_MAINTENANCE_DUE = "asset.maintenance_due"
    # System
    SYSTEM_ALERT = "system.alert"
    JOB_FAILED = "job.failed"
    # Custom
    CUSTOM_EVENT = "custom.event"


# =============================================================================
#  Webhook Schemas
# =============================================================================

class WebhookConfigCreate(BaseModel):
    """Schema for creating a webhook configuration."""
    name: str = Field(..., min_length=1, max_length=200, description="Webhook name")
    url: str = Field(..., min_length=1, max_length=2000, description="Webhook destination URL")
    method: WebhookMethod = Field(default=WebhookMethod.POST, description="HTTP method")
    events: list[WebhookEvent] = Field(..., min_length=1, description="Events to subscribe to")
    secret: Optional[str] = Field(None, min_length=16, max_length=256, description="HMAC signing secret")
    headers: Optional[dict[str, str]] = Field(default=None, description="Custom HTTP headers")
    retry_count: int = Field(default=3, ge=0, le=10, description="Max retry attempts")
    retry_delay_seconds: int = Field(default=60, ge=1, le=3600, description="Retry delay")
    timeout_seconds: int = Field(default=30, ge=1, le=120, description="Request timeout")
    is_active: bool = Field(default=True, description="Whether webhook is active")
    description: Optional[str] = Field(None, max_length=500, description="Webhook description")

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class WebhookConfigUpdate(BaseModel):
    """Schema for updating a webhook configuration."""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    url: Optional[str] = Field(None, min_length=1, max_length=2000)
    method: Optional[WebhookMethod] = None
    events: Optional[list[WebhookEvent]] = None
    secret: Optional[str] = Field(None, min_length=16, max_length=256)
    headers: Optional[dict[str, str]] = None
    retry_count: Optional[int] = Field(None, ge=0, le=10)
    retry_delay_seconds: Optional[int] = Field(None, ge=1, le=3600)
    timeout_seconds: Optional[int] = Field(None, ge=1, le=120)
    is_active: Optional[bool] = None
    description: Optional[str] = Field(None, max_length=500)


class WebhookConfigResponse(BaseModel):
    """Schema for webhook configuration response."""
    id: str
    name: str
    url: str
    method: WebhookMethod
    events: list[WebhookEvent]
    headers: dict[str, str]
    retry_count: int
    retry_delay_seconds: int
    timeout_seconds: int
    is_active: bool
    status: IntegrationStatus
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    delivery_count: int = 0
    failure_count: int = 0
    description: Optional[str] = None
    organization_id: str
    created_by: Optional[int] = None
    created_at: str
    updated_at: str


class WebhookDeliveryLog(BaseModel):
    """Schema for webhook delivery log entry."""
    id: str
    webhook_id: str
    event_type: str
    url: str
    method: str
    request_headers: dict[str, str]
    request_body: Any
    response_status: Optional[int] = None
    response_body: Optional[str] = None
    status: str  # success, failed, retrying
    attempt: int
    duration_ms: float
    error: Optional[str] = None
    timestamp: str


# =============================================================================
#  OAuth2 Schemas
# =============================================================================

class OAuth2ConfigCreate(BaseModel):
    """Schema for creating an OAuth2 client configuration."""
    name: str = Field(..., min_length=1, max_length=200)
    provider: str = Field(..., description="OAuth2 provider name (e.g., google, slack, salesforce)")
    client_id: str = Field(..., min_length=1)
    client_secret: str = Field(..., min_length=1)
    authorization_url: str = Field(..., description="OAuth2 authorization endpoint")
    token_url: str = Field(..., description="OAuth2 token endpoint")
    scopes: list[str] = Field(default_factory=list, description="OAuth2 scopes")
    redirect_url: str = Field("", description="OAuth2 redirect URL")
    extra_params: Optional[dict[str, str]] = None
    is_active: bool = True


class OAuth2ConfigResponse(BaseModel):
    """Schema for OAuth2 configuration response."""
    id: str
    name: str
    provider: str
    authorization_url: str
    scopes: list[str]
    redirect_url: str
    is_active: bool
    status: IntegrationStatus
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_expires_at: Optional[str] = None
    organization_id: str
    created_at: str
    updated_at: str


# =============================================================================
#  API Key Schemas
# =============================================================================

class ApiKeyCreate(BaseModel):
    """Schema for creating an API key."""
    name: str = Field(..., min_length=1, max_length=200, description="API key name")
    permissions: list[str] = Field(default_factory=list, description="API key permissions")
    allowed_ips: Optional[list[str]] = Field(default=None, description="Allowed IP addresses")
    expires_at: Optional[str] = Field(None, description="Expiration date")
    is_active: bool = True


class ApiKeyResponse(BaseModel):
    """Schema for API key response."""
    id: str
    name: str
    key_prefix: str = Field(..., description="First 8 chars of the key for identification")
    permissions: list[str]
    allowed_ips: Optional[list[str]] = None
    is_active: bool
    status: IntegrationStatus
    last_used_at: Optional[str] = None
    expires_at: Optional[str] = None
    organization_id: str
    created_by: Optional[int] = None
    created_at: str


class ApiKeyFullResponse(ApiKeyResponse):
    """Schema for API key response including the full key (only shown once)."""
    full_key: str = Field(..., description="Full API key (only shown on creation)")


# =============================================================================
#  Connector Schemas
# =============================================================================

class ConnectorConfigCreate(BaseModel):
    """Schema for creating an external system connector."""
    name: str = Field(..., min_length=1, max_length=200)
    connector_type: ConnectorType
    config: dict[str, Any] = Field(..., description="Connector-specific configuration")
    credentials: Optional[dict[str, Any]] = Field(None, description="Connector credentials")
    is_active: bool = True


class ConnectorConfigResponse(BaseModel):
    """Schema for connector configuration response."""
    id: str
    name: str
    connector_type: ConnectorType
    config: dict[str, Any]
    is_active: bool
    status: IntegrationStatus
    last_health_check: Optional[str] = None
    health_message: Optional[str] = None
    organization_id: str
    created_by: Optional[int] = None
    created_at: str
    updated_at: str


# =============================================================================
#  Integration Summary
# =============================================================================

class IntegrationSummary(BaseModel):
    """Schema for integration summary/dashboard."""
    total_webhooks: int = 0
    active_webhooks: int = 0
    total_oauth2: int = 0
    active_oauth2: int = 0
    total_api_keys: int = 0
    active_api_keys: int = 0
    total_connectors: int = 0
    active_connectors: int = 0
    total_deliveries: int = 0
    failed_deliveries: int = 0
    success_rate: float = 0.0
    recent_events: list[dict] = []


# =============================================================================
#  Integration Event
# =============================================================================

class IntegrationEvent(BaseModel):
    """Schema for an integration event to be dispatched."""
    event_type: WebhookEvent
    source_module: str
    source_id: Optional[str] = None
    organization_id: str
    payload: dict[str, Any]
    priority: str = "normal"  # low, normal, high, critical
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

