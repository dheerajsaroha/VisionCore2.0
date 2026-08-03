"""
integration.py — Integration Management API Router
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides REST endpoints for:
- Webhook configuration CRUD
- OAuth2 client management
- API key management
- External connector management
- Integration health monitoring
- Event dispatch
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_active_user
from app.db.database import get_db
from app.db.models.all_models import User
from app.schema.integration import (
    ApiKeyCreate,
    ConnectorConfigCreate,
    IntegrationEvent,
    IntegrationSummary,
    OAuth2ConfigCreate,
    WebhookConfigCreate,
    WebhookConfigUpdate,
    WebhookEvent,
)
from app.services.integration_engine import integration_engine
from app.services.webhook_dispatcher import webhook_dispatcher

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
#  Webhook Endpoints
# =============================================================================

@router.get("/webhooks", response_model=dict)
def list_webhooks(
    current_user: User = Depends(get_current_active_user),
):
    """List all webhook configurations for the current organization."""
    org_id = str(current_user.org_id)
    webhooks = integration_engine.get_webhooks_for_org(org_id)
    return {
        "total": len(webhooks),
        "webhooks": webhooks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/webhooks", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_webhook(
    config: WebhookConfigCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new webhook configuration."""
    org_id = str(current_user.org_id)
    webhook = integration_engine.create_webhook(
        org_id, config, created_by=current_user.id
    )
    return {
        "message": "Webhook created successfully",
        "webhook": webhook,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/webhooks/{webhook_id}", response_model=dict)
def get_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Get a webhook configuration by ID."""
    webhook = integration_engine.get_webhook(webhook_id)
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook {webhook_id} not found",
        )
    return {"webhook": webhook, "timestamp": datetime.now(timezone.utc).isoformat()}


@router.patch("/webhooks/{webhook_id}", response_model=dict)
def update_webhook(
    webhook_id: str,
    config: WebhookConfigUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """Update a webhook configuration."""
    webhook = integration_engine.update_webhook(
        webhook_id, config.model_dump(exclude_none=True)
    )
    if not webhook:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook {webhook_id} not found",
        )
    return {
        "message": "Webhook updated successfully",
        "webhook": webhook,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/webhooks/{webhook_id}", response_model=dict)
def delete_webhook(
    webhook_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a webhook configuration."""
    if not integration_engine.delete_webhook(webhook_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook {webhook_id} not found",
        )
    return {
        "message": "Webhook deleted successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/webhooks/{webhook_id}/deliveries", response_model=dict)
def get_webhook_deliveries(
    webhook_id: str,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
):
    """Get delivery logs for a webhook."""
    logs = integration_engine.get_delivery_logs(webhook_id, limit=limit)
    return {
        "total": len(logs),
        "deliveries": logs,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  OAuth2 Client Endpoints
# =============================================================================

@router.get("/oauth2", response_model=dict)
def list_oauth2_clients(
    current_user: User = Depends(get_current_active_user),
):
    """List all OAuth2 client configurations."""
    org_id = str(current_user.org_id)
    clients = integration_engine.get_oauth2_clients_for_org(org_id)
    return {
        "total": len(clients),
        "clients": clients,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/oauth2", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_oauth2_client(
    config: OAuth2ConfigCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new OAuth2 client configuration."""
    org_id = str(current_user.org_id)
    client = integration_engine.create_oauth2_client(org_id, config)
    return {
        "message": "OAuth2 client created successfully",
        "client": client,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/oauth2/{client_id}/exchange", response_model=dict)
def exchange_oauth2_token(
    client_id: str,
    code: str = Query(..., description="Authorization code"),
    redirect_uri: str = Query("", description="Redirect URI"),
    current_user: User = Depends(get_current_active_user),
):
    """Exchange an authorization code for OAuth2 tokens."""
    result = integration_engine.exchange_oauth2_token(client_id, code, redirect_uri)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token exchange failed",
        )
    return {
        "message": "Token exchange successful",
        "tokens": {"access_token": "***", "refresh_token": "***", "expires_in": result.get("expires_in")},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/oauth2/{client_id}/refresh", response_model=dict)
def refresh_oauth2_token(
    client_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Refresh an OAuth2 access token."""
    result = integration_engine.refresh_oauth2_token(client_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Token refresh failed",
        )
    return {
        "message": "Token refreshed successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/oauth2/{client_id}", response_model=dict)
def delete_oauth2_client(
    client_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete an OAuth2 client."""
    if not integration_engine.delete_oauth2_client(client_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth2 client {client_id} not found",
        )
    return {
        "message": "OAuth2 client deleted successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  API Key Endpoints
# =============================================================================

@router.get("/api-keys", response_model=dict)
def list_api_keys(
    current_user: User = Depends(get_current_active_user),
):
    """List all API keys for the organization."""
    org_id = str(current_user.org_id)
    keys = integration_engine.get_api_keys_for_org(org_id)
    return {
        "total": len(keys),
        "api_keys": keys,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api-keys", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_api_key(
    config: ApiKeyCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new API key. The full key is only shown once."""
    org_id = str(current_user.org_id)
    key = integration_engine.create_api_key(
        org_id, config, created_by=current_user.id
    )
    return {
        "message": "API key created successfully",
        "api_key": key,
        "warning": "Save the full_key now. It will not be shown again.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/api-keys/{key_id}/revoke", response_model=dict)
def revoke_api_key(
    key_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Revoke an API key."""
    if not integration_engine.revoke_api_key(key_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"API key {key_id} not found",
        )
    return {
        "message": "API key revoked successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  Connector Endpoints
# =============================================================================

@router.get("/connectors", response_model=dict)
def list_connectors(
    current_user: User = Depends(get_current_active_user),
):
    """List all external system connectors."""
    org_id = str(current_user.org_id)
    connectors = integration_engine.get_connectors_for_org(org_id)
    return {
        "total": len(connectors),
        "connectors": connectors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/connectors", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_connector(
    config: ConnectorConfigCreate,
    current_user: User = Depends(get_current_active_user),
):
    """Create a new external system connector."""
    org_id = str(current_user.org_id)
    connector = integration_engine.create_connector(
        org_id, config, created_by=current_user.id
    )
    return {
        "message": "Connector created successfully",
        "connector": connector,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/connectors/{connector_id}/test", response_model=dict)
def test_connector(
    connector_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Test a connector connection."""
    result = integration_engine.test_connector(connector_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    return {
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/connectors/{connector_id}", response_model=dict)
def delete_connector(
    connector_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Delete a connector."""
    if not integration_engine.delete_connector(connector_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Connector {connector_id} not found",
        )
    return {
        "message": "Connector deleted successfully",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  Event Dispatch
# =============================================================================

@router.post("/events/dispatch", response_model=dict)
def dispatch_event(
    event: IntegrationEvent,
    current_user: User = Depends(get_current_active_user),
):
    """Dispatch an integration event to all subscribed webhooks."""
    results = integration_engine.dispatch_event(event)
    return {
        "message": f"Event dispatched to {len(results)} webhook(s)",
        "event_type": event.event_type,
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  Dead Letter Queue
# =============================================================================

@router.get("/dead-letter", response_model=dict)
def get_dead_letter_queue(
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
):
    """Get the dead letter queue for failed webhook deliveries."""
    queue = webhook_dispatcher.get_dead_letter_queue(limit=limit)
    return {
        "total": len(queue),
        "entries": queue,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.post("/dead-letter/{delivery_id}/retry", response_model=dict)
def retry_dead_letter(
    delivery_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """Retry a dead letter delivery."""
    result = webhook_dispatcher.retry_dead_letter(delivery_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Delivery {delivery_id} not found in dead letter queue",
        )
    return {
        "message": "Retry attempted",
        "result": result,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.delete("/dead-letter", response_model=dict)
def clear_dead_letter_queue(
    current_user: User = Depends(get_current_active_user),
):
    """Clear the dead letter queue."""
    count = webhook_dispatcher.clear_dead_letter_queue()
    return {
        "message": f"Dead letter queue cleared ({count} entries removed)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
#  Integration Summary
# =============================================================================

@router.get("/summary", response_model=dict)
def get_integration_summary(
    current_user: User = Depends(get_current_active_user),
):
    """Get integration summary for the organization."""
    org_id = str(current_user.org_id)
    summary = integration_engine.get_summary(org_id)
    return {
        "summary": summary,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/events/available", response_model=dict)
def get_available_events():
    """Get all available webhook event types."""
    return {
        "events": [
            {"name": e.name, "value": e.value, "description": e.value.replace(".", " ").title()}
            for e in WebhookEvent
        ],
        "total": len(WebhookEvent),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
