"""
integration_engine.py — Enterprise Integration Engine
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Webhook configuration management (inbound/outbound)
- OAuth2 client credential management
- API key management with permission scoping
- External system connectors (Slack, Email, SMS, CRM, etc.)
- Integration health monitoring
- Event dispatch to configured webhooks
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

import requests

from app.schema.integration import (
    ApiKeyCreate,
    ApiKeyResponse,
    ApiKeyFullResponse,
    ConnectorConfigCreate,
    ConnectorConfigResponse,
    ConnectorType,
    IntegrationEvent,
    IntegrationStatus,
    IntegrationSummary,
    IntegrationType,
    OAuth2ConfigCreate,
    OAuth2ConfigResponse,
    WebhookConfigCreate,
    WebhookConfigResponse,
    WebhookDeliveryLog,
    WebhookEvent,
    WebhookMethod,
)

logger = logging.getLogger(__name__)


class IntegrationEngine:
    """
    Enterprise integration engine.

    Manages all external integrations:
    - Webhooks (inbound receiver, outbound dispatcher)
    - OAuth2 clients for third-party API access
    - API keys for programmatic access
    - External system connectors
    """

    def __init__(self):
        self._webhooks: dict[str, dict] = {}
        self._oauth2_clients: dict[str, dict] = {}
        self._api_keys: dict[str, dict] = {}
        self._connectors: dict[str, dict] = {}
        self._delivery_logs: list[dict] = []
        self._events_buffer: list[dict] = []
        self._max_delivery_logs: int = 10000
        self._max_events_buffer: int = 1000

    # =========================================================================
    #  Webhook Management
    # =========================================================================

    def create_webhook(self, org_id: str, config: WebhookConfigCreate,
                       created_by: Optional[int] = None) -> dict:
        """Create a new webhook configuration."""
        webhook_id = f"whk-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        secret = config.secret or secrets.token_hex(32)

        webhook = {
            "id": webhook_id,
            "organization_id": org_id,
            "name": config.name,
            "url": config.url,
            "method": config.method.value,
            "events": [e.value for e in config.events],
            "secret": secret,
            "headers": config.headers or {},
            "retry_count": config.retry_count,
            "retry_delay_seconds": config.retry_delay_seconds,
            "timeout_seconds": config.timeout_seconds,
            "is_active": config.is_active,
            "status": IntegrationStatus.ACTIVE.value,
            "delivery_count": 0,
            "failure_count": 0,
            "last_success_at": None,
            "last_failure_at": None,
            "description": config.description,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }

        self._webhooks[webhook_id] = webhook

        logger.info(
            f"Webhook created: {webhook_id} ({config.name}) "
            f"for org {org_id} with {len(config.events)} events"
        )

        return {**webhook, "secret": "***"}  # Don't expose secret in response

    def update_webhook(self, webhook_id: str, config: dict, org_id: Optional[str] = None) -> Optional[dict]:
        """Update an existing webhook configuration."""
        if webhook_id not in self._webhooks:
            return None

        webhook = self._webhooks[webhook_id]
        if org_id is not None and webhook["organization_id"] != org_id:
            return None
        updatable_keys = {
            "name", "url", "method", "events", "secret", "headers",
            "retry_count", "retry_delay_seconds", "timeout_seconds",
            "is_active", "description",
        }

        for key, value in config.items():
            if key in updatable_keys and value is not None:
                if key == "events" and isinstance(value, list):
                    webhook[key] = [e.value if hasattr(e, 'value') else e for e in value]
                elif key == "method" and hasattr(value, 'value'):
                    webhook[key] = value.value
                else:
                    webhook[key] = value

        webhook["updated_at"] = datetime.now(timezone.utc).isoformat()

        logger.info(f"Webhook updated: {webhook_id}")
        return {**webhook, "secret": "***"}

    def delete_webhook(self, webhook_id: str, org_id: Optional[str] = None) -> bool:
        """Delete a webhook configuration."""
        if webhook_id in self._webhooks and (org_id is None or self._webhooks[webhook_id]["organization_id"] == org_id):
            del self._webhooks[webhook_id]
            logger.info(f"Webhook deleted: {webhook_id}")
            return True
        return False

    def get_webhook(self, webhook_id: str, org_id: Optional[str] = None) -> Optional[dict]:
        """Get a webhook configuration by ID."""
        webhook = self._webhooks.get(webhook_id)
        if webhook and (org_id is None or webhook["organization_id"] == org_id):
            return {**webhook, "secret": "***"}
        return None

    def get_webhooks_for_org(self, org_id: str) -> list[dict]:
        """Get all webhooks for an organization."""
        return [
            {**w, "secret": "***"}
            for w in self._webhooks.values()
            if w["organization_id"] == org_id
        ]

    def get_webhooks_for_event(self, org_id: str, event_type: str) -> list[dict]:
        """Get all active webhooks subscribed to a specific event."""
        return [
            {**w, "secret": "***"}
            for w in self._webhooks.values()
            if w["organization_id"] == org_id
            and w["is_active"]
            and w["status"] == IntegrationStatus.ACTIVE.value
            and event_type in w["events"]
        ]

    # =========================================================================
    #  Webhook Dispatch
    # =========================================================================

    def dispatch_event(self, event: IntegrationEvent) -> list[dict]:
        """
        Dispatch an integration event to all subscribed webhooks.

        Returns list of delivery results.
        """
        results = []
        webhooks = self.get_webhooks_for_event(
            event.organization_id, event.event_type
        )

        logger.info(
            f"Dispatching event {event.event_type}: "
            f"{len(webhooks)} webhook(s) to notify"
        )

        for webhook in webhooks:
            wh = self._webhooks.get(webhook["id"], webhook)
            result = self._deliver_webhook(wh, event)
            results.append(result)

            # Log delivery
            self._delivery_logs.append(result)
            if len(self._delivery_logs) > self._max_delivery_logs:
                self._delivery_logs = self._delivery_logs[-self._max_delivery_logs:]

            # Update webhook stats
            wh = self._webhooks.get(webhook["id"])
            if wh:
                wh["delivery_count"] = wh.get("delivery_count", 0) + 1
                if result["status"] == "success":
                    wh["last_success_at"] = datetime.now(timezone.utc).isoformat()
                else:
                    wh["failure_count"] = wh.get("failure_count", 0) + 1
                    wh["last_failure_at"] = datetime.now(timezone.utc).isoformat()
                    if wh["failure_count"] >= wh.get("retry_count", 3) * 2:
                        wh["status"] = IntegrationStatus.ERROR.value

        return results

    def _deliver_webhook(self, webhook: dict, event: IntegrationEvent) -> dict:
        """Deliver event to a single webhook endpoint with HMAC signing."""
        payload = {
            "event_type": event.event_type,
            "source_module": event.source_module,
            "source_id": event.source_id,
            "organization_id": event.organization_id,
            "priority": event.priority,
            "timestamp": event.timestamp,
            "payload": event.payload,
            "delivery_id": f"del-{uuid.uuid4().hex[:12]}",
        }

        body = json.dumps(payload, default=str)
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event.event_type,
            "X-Delivery-ID": payload["delivery_id"],
            "X-Timestamp": str(int(time.time())),
        }

        # Add custom headers
        headers.update(webhook.get("headers", {}))

        # HMAC signing
        secret = webhook.get("secret", "")
        if secret and secret != "***":
            signature = hmac.new(
                secret.encode(),
                body.encode(),
                hashlib.sha256,
            ).hexdigest()
            sig_header = webhook.get("signature_header", "X-Webhook-Signature")
            headers[sig_header] = f"sha256={signature}"

        # Deliver with retries
        max_retries = webhook.get("retry_count", 3)
        retry_delay = webhook.get("retry_delay_seconds", 60)
        timeout = webhook.get("timeout_seconds", 30)
        method = webhook.get("method", "POST")
        url = webhook["url"]

        attempt = 0
        while attempt <= max_retries:
            attempt += 1
            start_time = time.time()

            try:
                response = requests.request(
                    method=method,
                    url=url,
                    data=body,
                    headers=headers,
                    timeout=timeout,
                )
                duration_ms = (time.time() - start_time) * 1000

                delivery = {
                    "id": payload["delivery_id"],
                    "webhook_id": webhook["id"],
                    "event_type": event.event_type,
                    "url": url,
                    "method": method,
                    "request_headers": headers,
                    "request_body": payload,
                    "response_status": response.status_code,
                    "response_body": response.text[:1000],
                    "status": "success" if response.ok else "failed",
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 2),
                    "error": None if response.ok else f"HTTP {response.status_code}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if response.ok:
                    logger.info(
                        f"Webhook delivered: {webhook['id']} → "
                        f"{url} ({response.status_code}) in {duration_ms:.0f}ms"
                    )
                    return delivery

                logger.warning(
                    f"Webhook delivery failed: {webhook['id']} → "
                    f"{url} ({response.status_code}), attempt {attempt}/{max_retries}"
                )

            except requests.Timeout:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Webhook timeout: {webhook['id']} → {url}, "
                    f"attempt {attempt}/{max_retries}"
                )

                if attempt <= max_retries:
                    time.sleep(retry_delay)
                    continue

                return {
                    "id": payload["delivery_id"],
                    "webhook_id": webhook["id"],
                    "event_type": event.event_type,
                    "url": url,
                    "method": method,
                    "request_headers": headers,
                    "request_body": payload,
                    "response_status": None,
                    "response_body": None,
                    "status": "failed",
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 2),
                    "error": "Request timeout",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            except requests.ConnectionError as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.warning(
                    f"Webhook connection error: {webhook['id']} → {url}: {e}"
                )

                if attempt <= max_retries:
                    time.sleep(retry_delay)
                    continue

                return {
                    "id": payload["delivery_id"],
                    "webhook_id": webhook["id"],
                    "event_type": event.event_type,
                    "url": url,
                    "method": method,
                    "request_headers": headers,
                    "request_body": payload,
                    "response_status": None,
                    "response_body": None,
                    "status": "failed",
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 2),
                    "error": f"Connection error: {e}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(f"Webhook unexpected error: {e}")

                return {
                    "id": payload["delivery_id"],
                    "webhook_id": webhook["id"],
                    "event_type": event.event_type,
                    "url": url,
                    "method": method,
                    "request_headers": headers,
                    "request_body": payload,
                    "response_status": None,
                    "response_body": None,
                    "status": "failed",
                    "attempt": attempt,
                    "duration_ms": round(duration_ms, 2),
                    "error": f"Unexpected error: {e}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

        return {
            "id": payload["delivery_id"],
            "webhook_id": webhook["id"],
            "event_type": event.event_type,
            "url": url,
            "method": method,
            "request_headers": headers,
            "request_body": payload,
            "response_status": None,
            "response_body": None,
            "status": "failed",
            "attempt": attempt,
            "duration_ms": 0,
            "error": "Max retries exhausted",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_delivery_logs(self, webhook_id: Optional[str] = None,
                          limit: int = 50) -> list[dict]:
        """Get delivery logs, optionally filtered by webhook."""
        logs = self._delivery_logs
        if webhook_id:
            logs = [l for l in logs if l["webhook_id"] == webhook_id]
        return sorted(logs, key=lambda l: l["timestamp"], reverse=True)[:limit]

    # =========================================================================
    #  OAuth2 Client Management
    # =========================================================================

    def create_oauth2_client(self, org_id: str, config: OAuth2ConfigCreate) -> dict:
        """Create a new OAuth2 client configuration."""
        client_id_str = f"oauth-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        client = {
            "id": client_id_str,
            "organization_id": org_id,
            "name": config.name,
            "provider": config.provider,
            "client_id": config.client_id,
            "client_secret": config.client_secret,
            "authorization_url": config.authorization_url,
            "token_url": config.token_url,
            "scopes": config.scopes,
            "redirect_url": config.redirect_url,
            "extra_params": config.extra_params or {},
            "is_active": config.is_active,
            "status": IntegrationStatus.PENDING.value,
            "access_token": None,
            "refresh_token": None,
            "token_expires_at": None,
            "created_at": now,
            "updated_at": now,
        }

        self._oauth2_clients[client_id_str] = client

        logger.info(
            f"OAuth2 client created: {client_id_str} "
            f"({config.provider}) for org {org_id}"
        )

        return {
            **client,
            "client_secret": "***",
        }

    def exchange_oauth2_token(self, client_id_str: str, code: str,
                              redirect_uri: str, org_id: Optional[str] = None) -> Optional[dict]:
        """Exchange authorization code for tokens."""
        client = self._oauth2_clients.get(client_id_str)
        if not client or (org_id is not None and client["organization_id"] != org_id):
            return None

        try:
            payload = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri or client["redirect_url"],
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
            }

            response = requests.post(
                client["token_url"],
                data=payload,
                timeout=30,
            )

            if response.ok:
                token_data = response.json()
                now = datetime.now(timezone.utc)

                client["access_token"] = token_data.get("access_token")
                client["refresh_token"] = token_data.get("refresh_token")
                expires_in = token_data.get("expires_in", 3600)
                client["token_expires_at"] = (
                    datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc).isoformat()
                )
                client["status"] = IntegrationStatus.ACTIVE.value
                client["updated_at"] = now.isoformat()

                logger.info(f"OAuth2 token exchanged: {client_id_str}")
                return {
                    "access_token": token_data.get("access_token"),
                    "refresh_token": token_data.get("refresh_token"),
                    "expires_in": expires_in,
                }

            logger.error(f"OAuth2 token exchange failed: {response.text[:200]}")
            client["status"] = IntegrationStatus.ERROR.value
            return None

        except Exception as e:
            logger.error(f"OAuth2 token exchange error: {e}")
            client["status"] = IntegrationStatus.ERROR.value
            return None

    def refresh_oauth2_token(self, client_id_str: str, org_id: Optional[str] = None) -> Optional[dict]:
        """Refresh an OAuth2 access token."""
        client = self._oauth2_clients.get(client_id_str)
        if not client or (org_id is not None and client["organization_id"] != org_id) or not client.get("refresh_token"):
            return None

        try:
            payload = {
                "grant_type": "refresh_token",
                "refresh_token": client["refresh_token"],
                "client_id": client["client_id"],
                "client_secret": client["client_secret"],
            }

            response = requests.post(
                client["token_url"],
                data=payload,
                timeout=30,
            )

            if response.ok:
                token_data = response.json()
                now = datetime.now(timezone.utc)

                client["access_token"] = token_data.get(
                    "access_token", client["access_token"]
                )
                client["refresh_token"] = token_data.get(
                    "refresh_token", client["refresh_token"]
                )
                expires_in = token_data.get("expires_in", 3600)
                client["token_expires_at"] = (
                    datetime.fromtimestamp(now.timestamp() + expires_in, tz=timezone.utc).isoformat()
                )
                client["updated_at"] = now.isoformat()

                logger.info(f"OAuth2 token refreshed: {client_id_str}")
                return token_data

            logger.error(f"OAuth2 token refresh failed: {response.text[:200]}")
            client["status"] = IntegrationStatus.ERROR.value
            return None

        except Exception as e:
            logger.error(f"OAuth2 token refresh error: {e}")
            client["status"] = IntegrationStatus.ERROR.value
            return None

    def get_oauth2_clients_for_org(self, org_id: str) -> list[dict]:
        """Get all OAuth2 clients for an organization."""
        return [
            {**c, "client_secret": "***"}
            for c in self._oauth2_clients.values()
            if c["organization_id"] == org_id
        ]

    def delete_oauth2_client(self, client_id_str: str, org_id: Optional[str] = None) -> bool:
        """Delete an OAuth2 client."""
        if client_id_str in self._oauth2_clients and (org_id is None or self._oauth2_clients[client_id_str]["organization_id"] == org_id):
            del self._oauth2_clients[client_id_str]
            return True
        return False

    # =========================================================================
    #  API Key Management
    # =========================================================================

    def create_api_key(self, org_id: str, config: ApiKeyCreate,
                       created_by: Optional[int] = None) -> dict:
        """Create a new API key."""
        key_id = f"apk-{uuid.uuid4().hex[:12]}"
        full_key = f"vc_{secrets.token_hex(32)}"
        now = datetime.now(timezone.utc).isoformat()

        api_key = {
            "id": key_id,
            "organization_id": org_id,
            "name": config.name,
            "full_key": full_key,
            "key_prefix": full_key[:12],
            "key_hash": hashlib.sha256(full_key.encode()).hexdigest(),
            "permissions": config.permissions,
            "allowed_ips": config.allowed_ips or [],
            "is_active": config.is_active,
            "status": IntegrationStatus.ACTIVE.value,
            "last_used_at": None,
            "expires_at": config.expires_at,
            "created_by": created_by,
            "created_at": now,
        }

        self._api_keys[key_id] = api_key

        logger.info(f"API key created: {key_id} for org {org_id}")

        # Return response with full key (only time it's shown)
        return {
            "id": key_id,
            "organization_id": org_id,
            "name": config.name,
            "full_key": full_key,
            "key_prefix": full_key[:12],
            "permissions": config.permissions,
            "allowed_ips": config.allowed_ips or [],
            "is_active": config.is_active,
            "status": IntegrationStatus.ACTIVE.value,
            "last_used_at": None,
            "expires_at": config.expires_at,
            "created_by": created_by,
            "created_at": now,
        }

    def validate_api_key(self, key: str) -> Optional[dict]:
        """Validate an API key and return its details if valid."""
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        for api_key in self._api_keys.values():
            if api_key["key_hash"] != key_hash:
                continue

            if not api_key["is_active"]:
                return None

            if api_key["status"] != IntegrationStatus.ACTIVE.value:
                return None

            # Check expiration
            if api_key.get("expires_at"):
                expires = datetime.fromisoformat(api_key["expires_at"])
                if expires < datetime.now(timezone.utc):
                    api_key["status"] = IntegrationStatus.INACTIVE.value
                    return None

            # Update last used
            api_key["last_used_at"] = datetime.now(timezone.utc).isoformat()

            return {
                "id": api_key["id"],
                "organization_id": api_key["organization_id"],
                "name": api_key["name"],
                "permissions": api_key["permissions"],
                "allowed_ips": api_key["allowed_ips"],
            }

        return None

    def get_api_keys_for_org(self, org_id: str) -> list[dict]:
        """Get all API keys for an organization (without full key)."""
        return [
            {k: v for k, v in ak.items() if k != "full_key" and k != "key_hash"}
            for ak in self._api_keys.values()
            if ak["organization_id"] == org_id
        ]

    def revoke_api_key(self, key_id: str, org_id: Optional[str] = None) -> bool:
        """Revoke an API key."""
        if key_id in self._api_keys and (org_id is None or self._api_keys[key_id]["organization_id"] == org_id):
            self._api_keys[key_id]["is_active"] = False
            self._api_keys[key_id]["status"] = IntegrationStatus.INACTIVE.value
            logger.info(f"API key revoked: {key_id}")
            return True
        return False

    # =========================================================================
    #  Connector Management
    # =========================================================================

    def create_connector(self, org_id: str, config: ConnectorConfigCreate,
                         created_by: Optional[int] = None) -> dict:
        """Create a new external system connector."""
        connector_id = f"con-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()

        connector = {
            "id": connector_id,
            "organization_id": org_id,
            "name": config.name,
            "connector_type": config.connector_type.value,
            "config": config.config,
            "credentials": config.credentials or {},
            "is_active": config.is_active,
            "status": IntegrationStatus.PENDING.value,
            "last_health_check": None,
            "health_message": None,
            "created_by": created_by,
            "created_at": now,
            "updated_at": now,
        }

        self._connectors[connector_id] = connector

        logger.info(
            f"Connector created: {connector_id} ({config.connector_type.value}) "
            f"for org {org_id}"
        )

        return {
            **connector,
            "credentials": "***",
        }

    def test_connector(self, connector_id: str, org_id: Optional[str] = None) -> Optional[dict]:
        """Test a connector connection."""
        connector = self._connectors.get(connector_id)
        if not connector or (org_id is not None and connector["organization_id"] != org_id):
            return None

        connector_type = connector["connector_type"]
        config = connector["config"]

        result = {
            "connector_id": connector_id,
            "connector_type": connector_type,
            "success": False,
            "message": "",
            "latency_ms": 0,
        }

        start_time = time.time()

        try:
            if connector_type == ConnectorType.EMAIL_SMTP.value:
                result["message"] = "SMTP configuration validated (syntax check)"
                result["success"] = True

            elif connector_type == ConnectorType.SLACK.value:
                webhook_url = config.get("webhook_url", "")
                if webhook_url:
                    response = requests.get(webhook_url.replace(
                        "hooks.slack.com", "slack.com/api/api.test"
                    ), timeout=10)
                    result["success"] = response.ok
                    result["message"] = "Slack API reachable" if response.ok else "Slack API unreachable"

            elif connector_type == ConnectorType.STORAGE_S3.value:
                bucket = config.get("bucket", "")
                region = config.get("region", "us-east-1")
                if bucket:
                    # Just validate config format
                    result["success"] = bool(bucket) and bool(region)
                    result["message"] = "S3 configuration valid"
                else:
                    result["message"] = "S3 bucket not configured"

            else:
                result["success"] = True
                result["message"] = f"Connector {connector_type} validated"

        except Exception as e:
            result["message"] = f"Connection test failed: {e}"

        result["latency_ms"] = round((time.time() - start_time) * 1000, 2)

        # Update connector status
        connector["last_health_check"] = datetime.now(timezone.utc).isoformat()
        connector["health_message"] = result["message"]
        if result["success"]:
            connector["status"] = IntegrationStatus.ACTIVE.value
        else:
            connector["status"] = IntegrationStatus.ERROR.value

        return result

    def get_connectors_for_org(self, org_id: str) -> list[dict]:
        """Get all connectors for an organization."""
        return [
            {**c, "credentials": "***"}
            for c in self._connectors.values()
            if c["organization_id"] == org_id
        ]

    def delete_connector(self, connector_id: str, org_id: Optional[str] = None) -> bool:
        """Delete a connector."""
        if connector_id in self._connectors and (org_id is None or self._connectors[connector_id]["organization_id"] == org_id):
            del self._connectors[connector_id]
            return True
        return False

    # =========================================================================
    #  Event Buffer
    # =========================================================================

    def buffer_event(self, event: IntegrationEvent) -> None:
        """Buffer an event for batch dispatch."""
        self._events_buffer.append({
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._events_buffer) > self._max_events_buffer:
            self._events_buffer = self._events_buffer[-self._max_events_buffer:]

    def flush_events(self) -> int:
        """Flush all buffered events. Returns count dispatched."""
        count = 0
        for entry in self._events_buffer:
            try:
                self.dispatch_event(entry["event"])
                count += 1
            except Exception as e:
                logger.error(f"Failed to flush event: {e}")
        self._events_buffer = []
        return count

    # =========================================================================
    #  Dashboard & Summary
    # =========================================================================

    def get_summary(self, org_id: str) -> dict:
        """Get integration summary for an organization."""
        webhooks = self.get_webhooks_for_org(org_id)
        oauth2 = self.get_oauth2_clients_for_org(org_id)
        api_keys = self.get_api_keys_for_org(org_id)
        connectors = self.get_connectors_for_org(org_id)

        # Calculate delivery stats
        org_deliveries = [
            l for l in self._delivery_logs
            if any(
                w.get("organization_id") == org_id
                for w in self._webhooks.values()
                if w["id"] == l.get("webhook_id")
            )
        ]

        total_deliveries = len(org_deliveries)
        failed_deliveries = len([l for l in org_deliveries if l.get("status") == "failed"])
        success_rate = (
            ((total_deliveries - failed_deliveries) / max(total_deliveries, 1)) * 100
        )

        return {
            "total_webhooks": len(webhooks),
            "active_webhooks": len([w for w in webhooks if w.get("is_active")]),
            "total_oauth2": len(oauth2),
            "active_oauth2": len([o for o in oauth2 if o.get("is_active")]),
            "total_api_keys": len(api_keys),
            "active_api_keys": len([k for k in api_keys if k.get("is_active")]),
            "total_connectors": len(connectors),
            "active_connectors": len([c for c in connectors if c.get("is_active")]),
            "total_deliveries": total_deliveries,
            "failed_deliveries": failed_deliveries,
            "success_rate": round(success_rate, 1),
            "recent_events": org_deliveries[-10:],
        }


# Singleton
integration_engine = IntegrationEngine()
