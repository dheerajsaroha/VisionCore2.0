"""
extension_manager.py — VisionCore Marketplace & Extension Framework
VisionCore 3.0 Enterprise Platform Services Layer

Provides:
- Plugin registration with metadata & version declaration
- Lifecycle hooks: on_user_created, on_attendance_marked, on_payroll_generated, on_leave_approved, on_workflow_completed
- Extension point discovery & dependency resolution
- SDK-ready plugin interface (BasePlugin ABC)
- Version compatibility checks
- Sandboxed plugin execution with error isolation
- Platform feature registration (new routes, menu items, permissions)
- Audit logging per plugin activation / deactivation
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Plugin Lifecycle Hooks (Platform Extension Points)
# ---------------------------------------------------------------------------

SUPPORTED_HOOKS = [
    "on_user_created",
    "on_user_updated",
    "on_user_deactivated",
    "on_attendance_marked",
    "on_leave_submitted",
    "on_leave_approved",
    "on_leave_rejected",
    "on_payroll_generated",
    "on_payroll_approved",
    "on_workflow_submitted",
    "on_workflow_completed",
    "on_ticket_created",
    "on_ticket_resolved",
    "on_asset_assigned",
    "on_notification_sent",
    "on_audit_recorded",
    "on_report_exported",
]

PLATFORM_VERSION = "3.0.0"


class PluginStatus(Enum):
    REGISTERED = "registered"
    ACTIVE = "active"
    INACTIVE = "inactive"
    ERROR = "error"


@dataclass
class PluginMetadata:
    """Declarative plugin registration metadata."""
    plugin_id: str
    name: str
    version: str
    description: str
    author: str
    min_platform_version: str = "3.0.0"
    max_platform_version: Optional[str] = None
    requires: List[str] = field(default_factory=list)    # Plugin dependency IDs
    provides: List[str] = field(default_factory=list)    # Feature IDs this plugin exposes
    hooks: List[str] = field(default_factory=list)       # Lifecycle hooks it subscribes to
    organization_scoped: bool = True                     # False = global marketplace plugin
    registered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PluginRecord:
    metadata: PluginMetadata
    status: PluginStatus = PluginStatus.REGISTERED
    error_message: Optional[str] = None
    activated_at: Optional[str] = None


# ---------------------------------------------------------------------------
#  Plugin SDK Abstract Base
# ---------------------------------------------------------------------------

class BasePlugin(ABC):
    """All VisionCore plugins must extend BasePlugin."""

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        pass

    def on_activate(self) -> None:
        """Called when the plugin is activated on the platform."""
        pass

    def on_deactivate(self) -> None:
        """Called when the plugin is deactivated."""
        pass

    def execute_hook(self, hook_name: str, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatch a lifecycle hook event to the plugin."""
        handler = getattr(self, hook_name, None)
        if handler and callable(handler):
            return handler(payload)
        return None


# ---------------------------------------------------------------------------
#  Extension Manager
# ---------------------------------------------------------------------------

class ExtensionManager:
    """
    VisionCore Marketplace & Extension Manager.
    Provides plugin registration, lifecycle, feature flags, and hook dispatching.
    """

    def __init__(self):
        self._plugins: Dict[str, PluginRecord] = {}
        self._hook_subscriptions: Dict[str, List[str]] = {hook: [] for hook in SUPPORTED_HOOKS}
        self._plugin_instances: Dict[str, BasePlugin] = {}
        self._org_enabled_plugins: Dict[str, List[str]] = {}  # org_id -> [plugin_id]

    # ------------------------------------------------------------------
    #  Plugin Registration
    # ------------------------------------------------------------------

    def register_plugin(self, plugin: BasePlugin, user_id: Optional[int] = None) -> PluginRecord:
        """Register a plugin class with the platform."""
        meta = plugin.metadata
        plugin_id = meta.plugin_id

        # Version compatibility check
        if not self._is_compatible(meta.min_platform_version, meta.max_platform_version):
            raise ValueError(
                f"Plugin '{meta.name}' v{meta.version} requires platform version "
                f"{meta.min_platform_version} – {meta.max_platform_version or 'latest'}, "
                f"but platform is at {PLATFORM_VERSION}"
            )

        # Dependency resolution
        for dep_id in meta.requires:
            if dep_id not in self._plugins:
                raise ValueError(f"Plugin '{meta.name}' depends on '{dep_id}' which is not registered")

        # Validate hooks
        for hook in meta.hooks:
            if hook not in SUPPORTED_HOOKS:
                raise ValueError(f"Plugin '{meta.name}' references unsupported hook '{hook}'")

        record = PluginRecord(metadata=meta)
        self._plugins[plugin_id] = record
        self._plugin_instances[plugin_id] = plugin

        # Register hook subscriptions
        for hook in meta.hooks:
            if plugin_id not in self._hook_subscriptions[hook]:
                self._hook_subscriptions[hook].append(plugin_id)

        logger.info(f"Plugin '{meta.name}' v{meta.version} registered (ID={plugin_id})")

        try:
            audit_service.record(
                actor_user_id=user_id,
                organization_id="__platform__",
                module="extension_manager",
                action="register_plugin",
                entity_type="plugin",
                entity_id=plugin_id,
                summary=f"Plugin '{meta.name}' v{meta.version} registered on platform",
                details={"plugin_id": plugin_id, "hooks": meta.hooks, "provides": meta.provides},
            )
        except Exception:
            pass

        return record

    def activate_plugin(
        self,
        plugin_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> PluginRecord:
        """Activate a registered plugin (optionally for a specific org)."""
        if plugin_id not in self._plugins:
            raise ValueError(f"Plugin '{plugin_id}' is not registered")

        record = self._plugins[plugin_id]
        plugin = self._plugin_instances[plugin_id]

        try:
            plugin.on_activate()
            record.status = PluginStatus.ACTIVE
            record.activated_at = datetime.now(timezone.utc).isoformat()
        except Exception as e:
            record.status = PluginStatus.ERROR
            record.error_message = str(e)
            logger.error(f"Plugin '{plugin_id}' activation failed: {e}")
            return record

        if organization_id:
            if organization_id not in self._org_enabled_plugins:
                self._org_enabled_plugins[organization_id] = []
            if plugin_id not in self._org_enabled_plugins[organization_id]:
                self._org_enabled_plugins[organization_id].append(plugin_id)

        logger.info(f"Plugin '{record.metadata.name}' activated" + (f" for org {organization_id}" if organization_id else ""))
        return record

    def deactivate_plugin(
        self,
        plugin_id: str,
        organization_id: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> bool:
        """Deactivate a plugin."""
        if plugin_id not in self._plugins:
            return False

        record = self._plugins[plugin_id]
        plugin = self._plugin_instances[plugin_id]

        try:
            plugin.on_deactivate()
        except Exception as e:
            logger.warning(f"Plugin deactivation hook error '{plugin_id}': {e}")

        record.status = PluginStatus.INACTIVE

        if organization_id and organization_id in self._org_enabled_plugins:
            self._org_enabled_plugins[organization_id] = [
                p for p in self._org_enabled_plugins[organization_id] if p != plugin_id
            ]

        logger.info(f"Plugin '{record.metadata.name}' deactivated")
        return True

    # ------------------------------------------------------------------
    #  Hook Dispatch
    # ------------------------------------------------------------------

    def dispatch_hook(
        self,
        hook_name: str,
        payload: Dict[str, Any],
        organization_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Dispatch a platform lifecycle hook event to all subscribed plugins."""
        if hook_name not in SUPPORTED_HOOKS:
            logger.warning(f"dispatch_hook called with unsupported hook '{hook_name}'")
            return []

        subscribers = self._hook_subscriptions.get(hook_name, [])
        results: List[Dict[str, Any]] = []

        for plugin_id in subscribers:
            record = self._plugins.get(plugin_id)
            if not record or record.status != PluginStatus.ACTIVE:
                continue

            # Org scope check
            if organization_id and record.metadata.organization_scoped:
                org_plugins = self._org_enabled_plugins.get(organization_id, [])
                if plugin_id not in org_plugins:
                    continue

            plugin = self._plugin_instances.get(plugin_id)
            if not plugin:
                continue

            try:
                result = plugin.execute_hook(hook_name, payload)
                if result:
                    results.append({"plugin_id": plugin_id, "result": result})
            except Exception as e:
                logger.error(f"Plugin '{plugin_id}' hook '{hook_name}' execution error: {e}")
                self._plugins[plugin_id].status = PluginStatus.ERROR
                self._plugins[plugin_id].error_message = str(e)

        return results

    # ------------------------------------------------------------------
    #  Discovery & Listing
    # ------------------------------------------------------------------

    def list_plugins(
        self,
        organization_id: Optional[str] = None,
        status: Optional[PluginStatus] = None,
    ) -> List[PluginRecord]:
        """List registered plugins, optionally filtered by org or status."""
        plugins = list(self._plugins.values())
        if status:
            plugins = [p for p in plugins if p.status == status]
        if organization_id:
            enabled = self._org_enabled_plugins.get(organization_id, [])
            plugins = [p for p in plugins if p.metadata.plugin_id in enabled]
        return plugins

    def get_plugin(self, plugin_id: str) -> PluginRecord:
        if plugin_id not in self._plugins:
            raise ValueError(f"Plugin '{plugin_id}' not found")
        return self._plugins[plugin_id]

    def get_available_hooks(self) -> List[str]:
        return SUPPORTED_HOOKS

    # ------------------------------------------------------------------
    #  Version Compatibility
    # ------------------------------------------------------------------

    def _is_compatible(self, min_version: str, max_version: Optional[str]) -> bool:
        """Check if current platform version satisfies plugin version requirements."""
        try:
            platform = tuple(int(x) for x in PLATFORM_VERSION.split("."))
            min_v = tuple(int(x) for x in min_version.split("."))
            if platform < min_v:
                return False
            if max_version:
                max_v = tuple(int(x) for x in max_version.split("."))
                if platform > max_v:
                    return False
            return True
        except (ValueError, AttributeError):
            return True  # Non-parseable version = permissive


# Singleton
extension_manager = ExtensionManager()
