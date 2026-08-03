"""
provider_base.py — Abstract Provider Interface for External Integrations
Sprint 6 — Phase C: Cloud Platform, Integrations & Enterprise Production Operations

Provides:
- Abstract base class for all external service providers
- Retry policy abstraction
- Rate limiting per provider
- OAuth2 token management
- Health check interface
"""
from __future__ import annotations

import abc
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class RetryPolicy:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        retryable_statuses: Optional[list[int]] = None,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.retryable_statuses = retryable_statuses or [429, 500, 502, 503, 504]


class RateLimitConfig:
    """Configuration for rate limiting."""
    
    def __init__(
        self,
        requests_per_second: float = 10.0,
        burst_size: int = 20,
        time_window_seconds: int = 60,
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.time_window_seconds = time_window_seconds


class ProviderHealth:
    """Health status of a provider connection."""
    
    def __init__(
        self,
        status: str = "unknown",
        latency_ms: float = 0.0,
        last_check: str = "",
        message: str = "",
    ):
        self.status = status  # healthy, degraded, down
        self.latency_ms = latency_ms
        self.last_check = last_check or datetime.now(timezone.utc).isoformat()
        self.message = message


class BaseProvider(abc.ABC):
    """
    Abstract base class for all external service providers.
    
    Subclasses must implement:
    - provider_name: str
    - _make_request()
    - _health_check()
    """

    provider_name: str = ""
    retry_policy: RetryPolicy = RetryPolicy()
    rate_limit: RateLimitConfig = RateLimitConfig()
    
    def __init__(self):
        self._health: ProviderHealth = ProviderHealth()
        self._last_request_time: float = 0.0
        self._request_count: int = 0
        self._error_count: int = 0

    @abc.abstractmethod
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        headers: Optional[dict] = None,
        params: Optional[dict] = None,
        data: Optional[Any] = None,
        timeout: int = 30,
    ) -> dict:
        """Make an HTTP request to the provider API."""
        ...

    @abc.abstractmethod
    async def _health_check(self) -> ProviderHealth:
        """Check provider connectivity."""
        ...

    async def health_check(self) -> ProviderHealth:
        """Public health check with caching."""
        self._health = await self._health_check()
        return self._health

    def get_health(self) -> ProviderHealth:
        """Get cached health status."""
        return self._health

    def get_stats(self) -> dict:
        """Get provider usage statistics."""
        return {
            "provider": self.provider_name,
            "request_count": self._request_count,
            "error_count": self._error_count,
            "health_status": self._health.status,
            "health_message": self._health.message,
        }

    def _enforce_rate_limit(self) -> None:
        """Enforce rate limiting by sleeping if needed."""
        if self.rate_limit.requests_per_second <= 0:
            return
        min_interval = 1.0 / self.rate_limit.requests_per_second
        elapsed = time.time() - self._last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self._last_request_time = time.time()


class Microsoft365Provider(BaseProvider):
    """Microsoft 365 / Graph API provider."""
    provider_name = "microsoft_365"
    
    def __init__(self, tenant_id: str = "", client_id: str = "", client_secret: str = ""):
        super().__init__()
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = ""
        self._token_expiry = 0.0
        self.base_url = "https://graph.microsoft.com/v1.0"
    
    async def _authenticate(self) -> str:
        """Get OAuth2 token for Microsoft Graph."""
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        token = await self._authenticate()
        req_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint}",
                headers=req_headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self._make_request("GET", "organization", timeout=10)
            latency = (time.time() - start) * 1000
            return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))
    
    async def get_users(self) -> list:
        return await self._make_request("GET", "users")
    
    async def get_groups(self) -> list:
        return await self._make_request("GET", "groups")
    
    async def send_email(self, subject: str, body: str, to: list[str]) -> dict:
        message = {
            "message": {
                "subject": subject,
                "body": {"contentType": "HTML", "content": body},
                "toRecipients": [{"emailAddress": {"address": addr}} for addr in to],
            }
        }
        return await self._make_request("POST", "me/sendMail", data=message)


class GoogleWorkspaceProvider(BaseProvider):
    """Google Workspace Admin SDK provider."""
    provider_name = "google_workspace"
    
    def __init__(self, service_account_key: dict = None, delegated_user: str = ""):
        super().__init__()
        self.service_account_key = service_account_key or {}
        self.delegated_user = delegated_user
        self.base_url = "https://admin.googleapis.com/admin/directory/v1"
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint}",
                headers=headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self._make_request("GET", "users", params={"maxResults": 1}, timeout=10)
            latency = (time.time() - start) * 1000
            return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))
    
    async def get_users(self, customer_id: str = "my_customer") -> list:
        return await self._make_request("GET", "users", params={"customer": customer_id})


class SlackProvider(BaseProvider):
    """Slack Web API provider."""
    provider_name = "slack"
    
    def __init__(self, bot_token: str = "", signing_secret: str = ""):
        super().__init__()
        self.bot_token = bot_token
        self.signing_secret = signing_secret
        self.base_url = "https://slack.com/api"
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        req_headers = {"Authorization": f"Bearer {self.bot_token}", **(headers or {})}
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint}",
                headers=req_headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            result = await self._make_request("GET", "api.test", timeout=10)
            latency = (time.time() - start) * 1000
            if result.get("ok"):
                return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
            return ProviderHealth(status="degraded", message=result.get("error", ""))
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))
    
    async def post_message(self, channel: str, text: str) -> dict:
        return await self._make_request("POST", "chat.postMessage", data={"channel": channel, "text": text})
    
    async def get_users(self) -> list:
        return await self._make_request("GET", "users.list")


class TeamsProvider(BaseProvider):
    """Microsoft Teams via Graph API provider."""
    provider_name = "microsoft_teams"
    
    def __init__(self, m365_provider: Microsoft365Provider = None):
        super().__init__()
        self._m365 = m365_provider or Microsoft365Provider()
        self.base_url = "https://graph.microsoft.com/v1.0"
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        token = await self._m365._authenticate()
        req_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint}",
                headers=req_headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self._make_request("GET", "teams", timeout=10)
            latency = (time.time() - start) * 1000
            return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))
    
    async def send_message(self, team_id: str, channel_id: str, message: str) -> dict:
        return await self._make_request(
            "POST", f"teams/{team_id}/channels/{channel_id}/messages",
            data={"body": {"content": message}},
        )


class ZoomProvider(BaseProvider):
    """Zoom API provider."""
    provider_name = "zoom"
    
    def __init__(self, account_id: str = "", client_id: str = "", client_secret: str = ""):
        super().__init__()
        self.account_id = account_id
        self.client_id = client_id
        self.client_secret = client_secret
        self._access_token = ""
        self._token_expiry = 0.0
        self.base_url = "https://api.zoom.us/v2"
    
    async def _authenticate(self) -> str:
        if self._access_token and time.time() < self._token_expiry:
            return self._access_token
        import httpx
        import base64
        creds = f"{self.client_id}:{self.client_secret}"
        encoded = base64.b64encode(creds.encode()).decode()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://zoom.us/oauth/token",
                data={"grant_type": "account_credentials", "account_id": self.account_id},
                headers={"Authorization": f"Basic {encoded}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            self._access_token = data["access_token"]
            self._token_expiry = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        token = await self._authenticate()
        req_headers = {"Authorization": f"Bearer {token}", **(headers or {})}
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint}",
                headers=req_headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self._make_request("GET", "users", params={"page_size": 1}, timeout=10)
            latency = (time.time() - start) * 1000
            return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))


class LDAPProvider(BaseProvider):
    """LDAP/Active Directory provider."""
    provider_name = "ldap"
    
    def __init__(self, server_uri: str = "", base_dn: str = "", bind_dn: str = "", bind_password: str = ""):
        super().__init__()
        self.server_uri = server_uri
        self.base_dn = base_dn
        self.bind_dn = bind_dn
        self.bind_password = bind_password
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        # LDAP doesn't use HTTP - this is a stub for the connector framework
        return {"status": "ldap_operation", "endpoint": endpoint}
    
    async def _health_check(self) -> ProviderHealth:
        try:
            import ldap3
            server = ldap3.Server(self.server_uri, get_info=ldap3.ALL)
            conn = ldap3.Connection(server, self.bind_dn, self.bind_password, auto_bind=True)
            conn.unbind()
            return ProviderHealth(status="healthy", message="LDAP connection successful")
        except ImportError:
            return ProviderHealth(status="degraded", message="ldap3 library not installed")
        except Exception as e:
            return ProviderHealth(status="down", message=str(e))
    
    async def search_users(self, search_filter: str = "(objectClass=user)") -> list:
        return await self._make_request("GET", f"search?filter={search_filter}")


class ActiveDirectoryProvider(LDAPProvider):
    """Active Directory provider (extends LDAP)."""
    provider_name = "active_directory"
    
    async def get_user_groups(self, username: str) -> list:
        return await self._make_request("GET", f"users/{username}/groups")


class GenericRESTProvider(BaseProvider):
    """Generic REST API provider for custom integrations."""
    provider_name = "generic_rest"
    
    def __init__(self, base_url: str = "", api_key: str = "", api_key_header: str = "X-API-Key"):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.api_key_header = api_key_header
    
    async def _make_request(self, method, endpoint, headers=None, params=None, data=None, timeout=30):
        req_headers = {self.api_key_header: self.api_key, **(headers or {})}
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.request(
                method, f"{self.base_url}/{endpoint.lstrip('/')}",
                headers=req_headers, params=params, json=data, timeout=timeout,
            )
            resp.raise_for_status()
            return resp.json()
    
    async def _health_check(self) -> ProviderHealth:
        try:
            start = time.time()
            await self._make_request("GET", "health", timeout=10)
            latency = (time.time() - start) * 1000
            return ProviderHealth(status="healthy", latency_ms=round(latency, 2))
        except Exception as e:
            return ProviderHealth(status="degraded", message=str(e))
